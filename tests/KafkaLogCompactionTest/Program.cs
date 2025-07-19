using Confluent.Kafka;
using System.Text.Json;

namespace KafkaLogCompactionTest
{
    class Program
    {
        private static readonly string BootstrapServers = "localhost:9092";
        private static readonly string TopicName = "processed-iot-data";
        private static readonly string ConsumerGroup = "log-compaction-test";

        static async Task Main(string[] args)
        {
            Console.WriteLine("Kafka Log Compaction Test - processed-iot-data Topic");
            Console.WriteLine("======================================================");
            Console.WriteLine($"Connecting to: {BootstrapServers}");
            Console.WriteLine($"Topic: {TopicName}");
            Console.WriteLine($"Consumer Group: {ConsumerGroup}");
            Console.WriteLine();
            Console.WriteLine("Monitoring for messages... Press Ctrl+C to exit");
            Console.WriteLine();

            var config = new ConsumerConfig
            {
                BootstrapServers = BootstrapServers,
                GroupId = ConsumerGroup,
                AutoOffsetReset = AutoOffsetReset.Earliest,
                EnableAutoCommit = true,
                SessionTimeoutMs = 6000,
                EnableAutoOffsetStore = false
            };

            using var consumer = new ConsumerBuilder<string, string>(config)
                .SetErrorHandler((_, e) => Console.WriteLine($"Error: {e.Reason}"))
                .Build();

            try
            {
                consumer.Subscribe(TopicName);
                
                var cancellationToken = new CancellationTokenSource();
                Console.CancelKeyPress += (_, e) => {
                    e.Cancel = true;
                    cancellationToken.Cancel();
                };

                while (!cancellationToken.Token.IsCancellationRequested)
                {
                    try
                    {
                        var consumeResult = consumer.Consume(cancellationToken.Token);
                        
                        if (consumeResult != null)
                        {
                            var timestamp = consumeResult.Message.Timestamp.UtcDateTime;
                            var key = consumeResult.Message.Key ?? "null";
                            var value = consumeResult.Message.Value ?? "null";
                            
                            Console.WriteLine($"[{timestamp:HH:mm:ss.fff}] Key: {key}");
                            
                            // Try to parse and pretty-print JSON value
                            try
                            {
                                var jsonDoc = JsonDocument.Parse(value);
                                var prettyJson = JsonSerializer.Serialize(jsonDoc, new JsonSerializerOptions 
                                { 
                                    WriteIndented = true 
                                });
                                Console.WriteLine($"Value: {prettyJson}");
                            }
                            catch
                            {
                                // If not JSON, just print raw value
                                Console.WriteLine($"Value: {value}");
                            }
                            
                            Console.WriteLine($"Partition: {consumeResult.Partition.Value}, Offset: {consumeResult.Offset.Value}");
                            Console.WriteLine(new string('-', 60));
                            
                            consumer.StoreOffset(consumeResult);
                        }
                    }
                    catch (ConsumeException e)
                    {
                        Console.WriteLine($"Consume error: {e.Error.Reason}");
                    }
                    catch (OperationCanceledException)
                    {
                        break;
                    }
                }
            }
            catch (Exception e)
            {
                Console.WriteLine($"Application error: {e.Message}");
            }
            finally
            {
                consumer.Close();
                Console.WriteLine("\nDisconnected from Kafka. Goodbye!");
            }
        }
    }
}