# scratch/run_smoke_test.py
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.orchestrator_agent.preflight import PreflightValidator
from agents.orchestrator_agent.agent import GrowthScoutOrchestrator

async def run_smoke_test() -> None:
    print("==================================================")
    print("GROWTHSCOUT AI — RUNTIME SMOKE TEST")
    print("==================================================")
    
    start_time = time.perf_counter()
    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED",
        "runtime_config": {},
        "health_checks": [],
        "connectivity": {},
        "worker_validation": {},
        "execution_timings_ms": {},
        "warnings": [],
        "failures": []
    }
    exit_code = 0

    # 1. Load config
    config_start = time.perf_counter()
    try:
        config = RuntimeConfig.load_from_env()
        report["runtime_config"] = {
            "config_version": config.config_version,
            "environment": config.environment,
            "loaded_at": config.loaded_at.isoformat(),
            "instance_id": config.instance_id
        }
        print(f"[*] Configuration loaded successfully (Instance: {config.instance_id}, Env: {config.environment})")
    except Exception as e:
        print(f"[!] Config load failed: {str(e)}")
        report["failures"].append(f"Config load failed: {str(e)}")
        write_report(report)
        sys.exit(1)
    report["execution_timings_ms"]["config_load"] = (time.perf_counter() - config_start) * 1000.0

    # 2. Preflight health checks
    health_start = time.perf_counter()
    print("[*] Running preflight health checks...")
    try:
        validator = PreflightValidator(config)
        health_results = await validator.run_checks()
        has_down = False
        for r in health_results:
            category_str = r.category.value if hasattr(r.category, "value") else r.category
            status_str = f"[{r.status}]"
            print(f"  - {category_str:<20} / {r.component:<25} {status_str:<8} {r.message} (latency: {r.latency_ms:.1f}ms)")
            report["health_checks"].append({
                "category": category_str,
                "component": r.component,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "message": r.message,
                "error_code": r.error_code.value if r.error_code else None
            })
            if r.status == "DOWN":
                has_down = True
                report["failures"].append(f"Component DOWN: {category_str} / {r.component} - {r.message}")
        
        if has_down:
            print("[!] Preflight health checks returned DOWN status.")
            exit_code = 2
        else:
            print("[*] All preflight health checks PASSED.")
    except Exception as e:
        print(f"[!] Preflight health check execution crashed: {str(e)}")
        report["failures"].append(f"Preflight validation crashed: {str(e)}")
        exit_code = 3
    report["execution_timings_ms"]["health_checks"] = (time.perf_counter() - health_start) * 1000.0

    # 3. Connectivity checks (only if keys are present)
    conn_start = time.perf_counter()
    print("[*] Testing external service connectivity...")
    
    # Google Maps Connectivity
    if config.google_maps_api_key:
        try:
            import googlemaps
            gmaps_start = time.perf_counter()
            gmaps = googlemaps.Client(key=config.google_maps_api_key, timeout=5.0)
            gmaps.reverse_geocode((40.714224, -73.961452))
            gmaps_latency = (time.perf_counter() - gmaps_start) * 1000.0
            print(f"  - google_maps             [CONNECTED] verified (latency: {gmaps_latency:.1f}ms)")
            report["connectivity"]["google_maps"] = {
                "status": "CONNECTED",
                "latency_ms": gmaps_latency,
                "error": None
            }
        except Exception as e:
            print(f"  - google_maps             [FAILED] {str(e)}")
            report["connectivity"]["google_maps"] = {
                "status": "FAILED",
                "latency_ms": 0.0,
                "error": str(e)
            }
            report["warnings"].append(f"Google Maps connection check failed: {str(e)}")
            if exit_code == 0:
                exit_code = 4
    else:
        print("  - google_maps             [SKIPPED] (No API key)")
        report["connectivity"]["google_maps"] = {
            "status": "SKIPPED",
            "latency_ms": 0.0,
            "error": "No API key configured."
        }

    # Scraper Connectivity (Test fetching a safe public domain)
    scraper_start = time.perf_counter()
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            res = await client.get("https://example.com", timeout=5.0)
        scraper_latency = (time.perf_counter() - scraper_start) * 1000.0
        print(f"  - scraper (example.com)   [CONNECTED] verified (latency: {scraper_latency:.1f}ms)")
        report["connectivity"]["scraper"] = {
            "status": "CONNECTED",
            "latency_ms": scraper_latency,
            "error": None
        }
    except Exception as e:
        print(f"  - scraper (example.com)   [FAILED] {str(e)}")
        report["connectivity"]["scraper"] = {
            "status": "FAILED",
            "latency_ms": 0.0,
            "error": str(e)
        }
        report["warnings"].append(f"Scraper connection check failed: {str(e)}")
        if exit_code == 0:
            exit_code = 4
    report["execution_timings_ms"]["connectivity_checks"] = (time.perf_counter() - conn_start) * 1000.0

    # 4. Worker validation
    worker_start = time.perf_counter()
    print("[*] Validating worker agent registrations...")
    try:
        # Build orchestrator with preflight checks bypassed for initialization
        orchestrator = await GrowthScoutOrchestrator.initialize(config=config, bypass_preflight=True)
        registry = orchestrator.deps.worker_registry
        
        workers = ["business_discovery_agent", "website_analysis_agent", "opportunity_agent", "growth_intelligence_agent"]
        for worker in workers:
            try:
                agent = registry.get(worker)
                print(f"  - {worker:<25} [REGISTERED] model: {agent.model}")
                report["worker_validation"][worker] = "PASSED"
            except Exception as e:
                print(f"  - {worker:<25} [FAILED] {str(e)}")
                report["worker_validation"][worker] = "FAILED"
                report["failures"].append(f"Worker registry failure for {worker}: {str(e)}")
                exit_code = 5
                
        # Write metrics snapshot json
        try:
            metrics_collector = orchestrator.services.metrics_collector
            cache_stats = {
                "hits": orchestrator.services.cache_manager.hits,
                "misses": orchestrator.services.cache_manager.misses,
                "evictions": orchestrator.services.cache_manager.evictions,
                "expired_entries": orchestrator.services.cache_manager.expired_entries,
            }
            snapshot = metrics_collector.snapshot("smoke_test_session", cache_stats=cache_stats)
            snapshot_path = "scratch/metrics_snapshot.json"
            with open(snapshot_path, "w") as f:
                json.dump(snapshot.model_dump(), f, indent=2)
            print(f"[*] Metrics snapshot saved to {snapshot_path}")
        except Exception as e:
            print(f"[!] Failed to write metrics snapshot: {str(e)}")
            
    except Exception as e:
        print(f"[!] Worker registry validation failed: {str(e)}")
        report["failures"].append(f"Worker validation error: {str(e)}")
        exit_code = 5
    report["execution_timings_ms"]["worker_runs"] = (time.perf_counter() - worker_start) * 1000.0

    # End
    total_time = (time.perf_counter() - start_time) * 1000.0
    report["execution_timings_ms"]["total"] = total_time
    
    if len(report["failures"]) == 0 and exit_code == 0:
        report["status"] = "PASSED"
        print(f"\n[+] SMOKE TEST PASSED (Total duration: {total_time:.1f}ms)")
    else:
        print(f"\n[!] SMOKE TEST FAILED with status code {exit_code}. Check scratch/smoke_test_report.json.")
        
    write_report(report)
    sys.exit(exit_code)

def write_report(report: dict) -> None:
    os.makedirs("scratch", exist_ok=True)
    report_path = "scratch/smoke_test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[*] Machine-readable report saved to {report_path}")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
