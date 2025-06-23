import os
import time
import logging
from typing import Dict, List, Any
import docker
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IoT Architecture Health Monitor", version="1.0.0")

# Prometheus metrics
container_status_gauge = Gauge('container_status', 'Container status (1=running, 0=stopped)', ['container_name', 'service'])
container_cpu_usage = Gauge('container_cpu_usage_percent', 'Container CPU usage percentage', ['container_name'])
container_memory_usage = Gauge('container_memory_usage_bytes', 'Container memory usage in bytes', ['container_name'])
container_restart_count = Gauge('container_restart_count', 'Container restart count', ['container_name'])
service_health_check = Counter('service_health_checks_total', 'Total health checks performed', ['service', 'status'])
response_time_histogram = Histogram('health_check_duration_seconds', 'Health check response time', ['service'])

class HealthMonitor:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.monitored_services = [
            'mosquitto', 'kafka', 'zookeeper', 'postgres', 'timescaledb',
            'mqtt-kafka-connector', 'data-processor', 'kafka-timescale-sink', 'f2-simulator'
        ]
        
    def get_container_stats(self) -> Dict[str, Any]:
        """Get stats for all monitored containers."""
        stats = {}
        
        try:
            containers = self.docker_client.containers.list(all=True)
            
            for container in containers:
                name = container.name
                if any(service in name for service in self.monitored_services):
                    try:
                        # Basic container info
                        is_running = container.status == 'running'
                        restart_count = container.attrs['RestartCount']
                        
                        # Update Prometheus metrics
                        container_status_gauge.labels(container_name=name, service=self._get_service_name(name)).set(1 if is_running else 0)
                        container_restart_count.labels(container_name=name).set(restart_count)
                        
                        # Get container stats if running
                        if is_running:
                            container_stats = container.stats(stream=False)
                            cpu_percent = self._calculate_cpu_percent(container_stats)
                            memory_usage = container_stats['memory_stats'].get('usage', 0)
                            
                            container_cpu_usage.labels(container_name=name).set(cpu_percent)
                            container_memory_usage.labels(container_name=name).set(memory_usage)
                        
                        stats[name] = {
                            'status': container.status,
                            'running': is_running,
                            'restart_count': restart_count,
                            'created': container.attrs['Created'],
                            'image': container.image.tags[0] if container.image.tags else 'unknown'
                        }
                        
                        if is_running:
                            stats[name]['cpu_percent'] = cpu_percent
                            stats[name]['memory_usage'] = memory_usage
                            
                    except Exception as e:
                        logger.error(f"Error getting stats for container {name}: {e}")
                        stats[name] = {'status': 'error', 'error': str(e)}
                        
        except Exception as e:
            logger.error(f"Error connecting to Docker: {e}")
            return {'error': f'Docker connection failed: {e}'}
            
        return stats
    
    def _get_service_name(self, container_name: str) -> str:
        """Extract service name from container name."""
        for service in self.monitored_services:
            if service in container_name:
                return service
        return 'unknown'
    
    def _calculate_cpu_percent(self, stats: Dict) -> float:
        """Calculate CPU usage percentage from container stats."""
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
                return round(cpu_percent, 2)
        except (KeyError, ZeroDivisionError):
            pass
        return 0.0
    
    def check_service_connectivity(self) -> Dict[str, Any]:
        """Check connectivity to key services."""
        connectivity = {}
        
        # Check PostgreSQL
        try:
            postgres_container = self.docker_client.containers.get('device-params-db')
            if postgres_container.status == 'running':
                result = postgres_container.exec_run('pg_isready -U iot_user')
                connectivity['postgres'] = {
                    'status': 'healthy' if result.exit_code == 0 else 'unhealthy',
                    'response': result.output.decode().strip()
                }
                service_health_check.labels(service='postgres', status='healthy' if result.exit_code == 0 else 'unhealthy').inc()
            else:
                connectivity['postgres'] = {'status': 'not_running'}
                service_health_check.labels(service='postgres', status='not_running').inc()
        except Exception as e:
            connectivity['postgres'] = {'status': 'error', 'error': str(e)}
            service_health_check.labels(service='postgres', status='error').inc()
        
        # Check TimescaleDB
        try:
            timescale_container = self.docker_client.containers.get('timescale-db')
            if timescale_container.status == 'running':
                result = timescale_container.exec_run('pg_isready -U ts_user')
                connectivity['timescaledb'] = {
                    'status': 'healthy' if result.exit_code == 0 else 'unhealthy',
                    'response': result.output.decode().strip()
                }
                service_health_check.labels(service='timescaledb', status='healthy' if result.exit_code == 0 else 'unhealthy').inc()
            else:
                connectivity['timescaledb'] = {'status': 'not_running'}
                service_health_check.labels(service='timescaledb', status='not_running').inc()
        except Exception as e:
            connectivity['timescaledb'] = {'status': 'error', 'error': str(e)}
            service_health_check.labels(service='timescaledb', status='error').inc()
        
        # Check Kafka
        try:
            kafka_container = self.docker_client.containers.get('kafka')
            if kafka_container.status == 'running':
                result = kafka_container.exec_run('kafka-topics --bootstrap-server localhost:9092 --list')
                connectivity['kafka'] = {
                    'status': 'healthy' if result.exit_code == 0 else 'unhealthy',
                    'topics_count': len(result.output.decode().strip().split('\n')) if result.exit_code == 0 else 0
                }
                service_health_check.labels(service='kafka', status='healthy' if result.exit_code == 0 else 'unhealthy').inc()
            else:
                connectivity['kafka'] = {'status': 'not_running'}
                service_health_check.labels(service='kafka', status='not_running').inc()
        except Exception as e:
            connectivity['kafka'] = {'status': 'error', 'error': str(e)}
            service_health_check.labels(service='kafka', status='error').inc()
        
        return connectivity

monitor = HealthMonitor()

@app.get("/")
async def root():
    return {"message": "IoT Architecture Health Monitor", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Overall health check endpoint."""
    start_time = time.time()
    
    try:
        container_stats = monitor.get_container_stats()
        connectivity = monitor.check_service_connectivity()
        
        # Count healthy services
        running_containers = sum(1 for stats in container_stats.values() 
                               if isinstance(stats, dict) and stats.get('running', False))
        total_containers = len(container_stats)
        
        healthy_services = sum(1 for conn in connectivity.values() 
                             if isinstance(conn, dict) and conn.get('status') == 'healthy')
        total_services = len(connectivity)
        
        health_status = {
            'overall_status': 'healthy' if running_containers == total_containers and healthy_services == total_services else 'degraded',
            'timestamp': time.time(),
            'containers': {
                'running': running_containers,
                'total': total_containers
            },
            'services': {
                'healthy': healthy_services,
                'total': total_services
            },
            'details': {
                'containers': container_stats,
                'connectivity': connectivity
            }
        }
        
        # Record response time
        response_time = time.time() - start_time
        response_time_histogram.labels(service='health_check').observe(response_time)
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

@app.get("/containers")
async def get_containers():
    """Get detailed container information."""
    return monitor.get_container_stats()

@app.get("/connectivity")
async def get_connectivity():
    """Get service connectivity status."""
    return monitor.check_service_connectivity()

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    # Update metrics before serving
    monitor.get_container_stats()
    monitor.check_service_connectivity()
    
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/system")
async def get_system_info():
    """Get system resource information."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': (disk.used / disk.total) * 100
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"System info failed: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)