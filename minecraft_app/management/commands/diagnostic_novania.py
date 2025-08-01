#!/usr/bin/env python3
"""
Script de diagnostic RCON spécialement adapté pour Novania
Utilisez: python diagnostic_novania.py
"""

import socket
import time
import os
from mcrcon import MCRcon
import threading

# Configuration Novania
MINECRAFT_RCON_HOST = "91.197.6.92"
MINECRAFT_RCON_PORT = 30011
MINECRAFT_RCON_PASSWORD = "JKL159-cPPp,;?"

def test_network_latency(host, port, iterations=5):
    """Test de latence réseau"""
    print(f"🔍 Test de latence réseau vers {host}:{port}")
    
    latencies = []
    
    for i in range(iterations):
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, port))
            latency = (time.time() - start_time) * 1000  # en ms
            sock.close()
            
            if result == 0:
                latencies.append(latency)
                print(f"  Test {i+1}: ✅ {latency:.2f}ms")
            else:
                print(f"  Test {i+1}: ❌ Connexion échouée")
            
            time.sleep(1)
        except Exception as e:
            print(f"  Test {i+1}: ❌ {e}")
    
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        print(f"📊 Latence: moy={avg_latency:.2f}ms, min={min_latency:.2f}ms, max={max_latency:.2f}ms")
        
        if avg_latency > 1000:
            print("⚠️  Latence élevée détectée - cela peut causer des timeouts RCON")
        
        return avg_latency < 1000
    else:
        print("❌ Aucune connexion réussie")
        return False

def test_rcon_with_timeout(host, port, password, timeout):
    """Test RCON avec timeout spécifique"""
    try:
        mcr = MCRcon(host, password, port, tlsmode=0)
        mcr.socket.settimeout(timeout)
        
        start_time = time.time()
        mcr.connect()
        connect_time = time.time() - start_time
        
        start_time = time.time()
        response = mcr.command("list")
        command_time = time.time() - start_time
        
        mcr.disconnect()
        
        print(f"  Timeout {timeout}s: ✅ connect={connect_time:.3f}s, command={command_time:.3f}s")
        return True, connect_time, command_time
    except Exception as e:
        print(f"  Timeout {timeout}s: ❌ {e}")
        return False, 0, 0

def test_concurrent_connections(host, port, password, num_threads=3):
    """Test de connexions RCON concurrentes"""
    print(f"🔍 Test de {num_threads} connexions RCON concurrentes")
    
    results = []
    threads = []
    
    def rcon_worker(thread_id):
        try:
            mcr = MCRcon(host, password, port, tlsmode=0)
            mcr.socket.settimeout(15)
            mcr.connect()
            
            response = mcr.command("list")
            mcr.disconnect()
            
            results.append((thread_id, True, "OK"))
            print(f"  Thread {thread_id}: ✅")
        except Exception as e:
            results.append((thread_id, False, str(e)))
            print(f"  Thread {thread_id}: ❌ {e}")
    
    # Lancer les threads
    for i in range(num_threads):
        thread = threading.Thread(target=rcon_worker, args=(i+1,))
        threads.append(thread)
        thread.start()
        time.sleep(0.2)  # Petit délai entre les démarrages
    
    # Attendre tous les threads
    for thread in threads:
        thread.join()
    
    success_count = sum(1 for _, success, _ in results if success)
    print(f"📊 Résultat concurrent: {success_count}/{num_threads} connexions réussies")
    
    return success_count == num_threads

def test_rcon_reliability(host, port, password, iterations=20):
    """Test de fiabilité RCON sur plusieurs connexions"""
    print(f"🔍 Test de fiabilité RCON ({iterations} connexions séquentielles)")
    
    success_count = 0
    failure_types = {}
    
    for i in range(iterations):
        try:
            mcr = MCRcon(host, password, port, tlsmode=0)
            mcr.socket.settimeout(15)
            mcr.connect()
            
            # Test avec une commande qui peut prendre du temps
            response = mcr.command("list")
            
            mcr.disconnect()
            success_count += 1
            
            if (i + 1) % 5 == 0:
                print(f"  Progression: {i+1}/{iterations} (✅ {success_count})")
            
            # Délai entre connexions pour simuler l'usage réel
            time.sleep(0.5)
            
        except Exception as e:
            error_type = type(e).__name__
            failure_types[error_type] = failure_types.get(error_type, 0) + 1
            
            if (i + 1) % 5 == 0:
                print(f"  Progression: {i+1}/{iterations} (✅ {success_count}, ❌ {i+1-success_count})")
    
    print(f"📊 Résultat final: {success_count}/{iterations} réussies ({success_count/iterations*100:.1f}%)")
    
    if failure_types:
        print("🔍 Types d'erreurs rencontrées:")
        for error_type, count in failure_types.items():
            print(f"  {error_type}: {count} fois")
    
    return success_count / iterations >= 0.9  # 90% de réussite minimum

def main():
    print("🚀 DIAGNOSTIC RCON NOVANIA")
    print("=" * 50)
    print(f"Host: {MINECRAFT_RCON_HOST}")
    print(f"Port: {MINECRAFT_RCON_PORT}")
    print(f"Password: {'*' * len(MINECRAFT_RCON_PASSWORD)}")
    print()
    
    # Tests séquentiels
    tests_results = []
    
    # Test 1: Latence réseau
    print("=" * 60)
    latency_ok = test_network_latency(MINECRAFT_RCON_HOST, MINECRAFT_RCON_PORT)
    tests_results.append(("Latence réseau", latency_ok))
    
    # Test 2: RCON avec différents timeouts
    print("\n" + "=" * 60)
    print("🔍 Test RCON avec différents timeouts")
    timeout_results = []
    for timeout in [5, 10, 15, 20]:
        success, connect_time, command_time = test_rcon_with_timeout(
            MINECRAFT_RCON_HOST, MINECRAFT_RCON_PORT, MINECRAFT_RCON_PASSWORD, timeout
        )
        timeout_results.append(success)
    
    timeout_ok = any(timeout_results)
    tests_results.append(("RCON timeouts", timeout_ok))
    
    # Test 3: Connexions concurrentes
    print("\n" + "=" * 60)
    concurrent_ok = test_concurrent_connections(
        MINECRAFT_RCON_HOST, MINECRAFT_RCON_PORT, MINECRAFT_RCON_PASSWORD
    )
    tests_results.append(("Connexions concurrentes", concurrent_ok))
    
    # Test 4: Fiabilité
    print("\n" + "=" * 60)
    reliability_ok = test_rcon_reliability(
        MINECRAFT_RCON_HOST, MINECRAFT_RCON_PORT, MINECRAFT_RCON_PASSWORD, 15
    )
    tests_results.append(("Fiabilité RCON", reliability_ok))
    
    # Résumé final
    print(f"\n{'='*60}")
    print("📋 RÉSUMÉ FINAL")
    print("=" * 60)
    
    for test_name, success in tests_results:
        status = "✅ RÉUSSI" if success else "❌ ÉCHOUÉ"
        print(f"{test_name:.<30} {status}")
    
    # Recommandations spécifiques
    print(f"\n{'='*60}")
    print("🔧 RECOMMANDATIONS SPÉCIFIQUES")
    print("=" * 60)
    
    if not tests_results[0][1]:  # Latence
        print("🔧 Problème de latence réseau:")
        print("   - Vérifiez la connexion Internet du serveur web")
        print("   - Le serveur Minecraft peut être surchargé")
        print("   - Considérez un serveur web plus proche géographiquement")
    
    if not tests_results[1][1]:  # Timeouts
        print("🔧 Problème de timeouts RCON:")
        print("   - Augmentez MINECRAFT_RCON_TIMEOUT à 20 ou 30")
        print("   - Vérifiez les logs du serveur Minecraft")
        print("   - Le serveur peut être en surcharge CPU")
    
    if not tests_results[2][1]:  # Concurrent
        print("🔧 Problème de connexions concurrentes:")
        print("   - Limitez le nombre de connexions RCON simultanées")
        print("   - Implémentez un système de queue pour les commandes")
        print("   - Ajoutez des délais entre les connexions")
    
    if not tests_results[3][1]:  # Reliability
        print("🔧 Problème de fiabilité:")
        print("   - Augmentez MINECRAFT_RCON_MAX_RETRIES à 5")
        print("   - Augmentez MINECRAFT_RCON_RETRY_DELAY à 10")
        print("   - Implémentez un circuit breaker")
        print("   - Surveillez les logs du serveur Minecraft")
    
    # Configuration recommandée
    all_passed = all(result[1] for result in tests_results)
    if not all_passed:
        print(f"\n{'='*60}")
        print("⚙️  CONFIGURATION .ENV RECOMMANDÉE")
        print("=" * 60)
        print("MINECRAFT_RCON_TIMEOUT=20")
        print("MINECRAFT_RCON_MAX_RETRIES=5") 
        print("MINECRAFT_RCON_RETRY_DELAY=10")
        print()
        print("Ajoutez ces lignes à votre fichier .env et redémarrez votre application.")
    else:
        print("\n🎉 Tous les tests sont réussis ! RCON fonctionne de manière optimale.")

if __name__ == "__main__":
    main()