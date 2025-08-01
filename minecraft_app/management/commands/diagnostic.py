from django.core.management.base import BaseCommand
import socket
import time
import threading
from django.conf import settings

class Command(BaseCommand):
    help = 'Diagnostic RCON complet pour Novania'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quick',
            action='store_true',
            help='Test rapide seulement',
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 DIAGNOSTIC RCON NOVANIA")
        self.stdout.write("=" * 50)
        
        # Configuration
        host = settings.MINECRAFT_RCON_HOST
        port = settings.MINECRAFT_RCON_PORT
        password = settings.MINECRAFT_RCON_PASSWORD
        
        self.stdout.write(f"Host: {host}")
        self.stdout.write(f"Port: {port}")
        self.stdout.write(f"Password: {'*' * len(password)}")
        self.stdout.write("")
        
        if options['quick']:
            self.run_quick_tests(host, port, password)
        else:
            self.run_full_tests(host, port, password)

    def run_quick_tests(self, host, port, password):
        """Tests rapides essentiels"""
        self.stdout.write("🔍 TESTS RAPIDES")
        self.stdout.write("=" * 30)
        
        # Test 1: Connectivité
        if self.test_connectivity(host, port):
            self.stdout.write(self.style.SUCCESS("✅ Connectivité réseau OK"))
        else:
            self.stdout.write(self.style.ERROR("❌ Connectivité réseau ÉCHEC"))
            return
        
        # Test 2: RCON avec notre nouvelle implémentation
        if self.test_rcon_new_implementation():
            self.stdout.write(self.style.SUCCESS("✅ RCON nouvelle implémentation OK"))
        else:
            self.stdout.write(self.style.ERROR("❌ RCON nouvelle implémentation ÉCHEC"))

    def run_full_tests(self, host, port, password):
        """Tests complets"""
        tests_results = []
        
        # Test 1: Latence
        self.stdout.write("=" * 60)
        self.stdout.write("🔍 Test de latence réseau")
        latency_ok = self.test_network_latency(host, port)
        tests_results.append(("Latence réseau", latency_ok))
        
        # Test 2: RCON avec nouvelle implémentation
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("🔍 Test RCON nouvelle implémentation")
        rcon_ok = self.test_rcon_new_implementation()
        tests_results.append(("RCON nouvelle implémentation", rcon_ok))
        
        # Test 3: Implémentation custom directe
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("🔍 Test RCON implémentation custom")
        custom_ok = self.test_rcon_custom_direct(host, port, password)
        tests_results.append(("RCON custom direct", custom_ok))
        
        # Test 4: Fiabilité avec nouvelle implémentation
        if rcon_ok or custom_ok:
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("🔍 Test de fiabilité (5 connexions)")
            reliability_ok = self.test_reliability_new(5)
            tests_results.append(("Fiabilité", reliability_ok))
        else:
            tests_results.append(("Fiabilité", False))
        
        # Résumé
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("📋 RÉSUMÉ FINAL")
        self.stdout.write("=" * 60)
        
        for test_name, success in tests_results:
            if success:
                self.stdout.write(f"{test_name:.<30} " + self.style.SUCCESS("✅ RÉUSSI"))
            else:
                self.stdout.write(f"{test_name:.<30} " + self.style.ERROR("❌ ÉCHOUÉ"))
        
        # Recommandations
        self.show_recommendations(tests_results)

    def test_connectivity(self, host, port):
        """Test de connectivité basique"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

    def test_rcon_new_implementation(self):
        """Test avec la nouvelle implémentation dans minecraft_service.py"""
        try:
            from minecraft_app.minecraft_service import test_rcon_connection
            result = test_rcon_connection()
            if result:
                self.stdout.write("  ✅ test_rcon_connection() réussi")
            else:
                self.stdout.write("  ❌ test_rcon_connection() échoué")
            return result
        except Exception as e:
            self.stdout.write(f"  ❌ Erreur dans test_rcon_connection: {e}")
            return False

    def test_rcon_custom_direct(self, host, port, password):
        """Test direct avec notre classe SimpleRCON"""
        try:
            from minecraft_app.minecraft_service import SimpleRCON
            
            self.stdout.write("  Test avec SimpleRCON...")
            rcon = SimpleRCON(host, password, port)
            rcon.connect()
            
            response = rcon.command("list")
            rcon.disconnect()
            
            self.stdout.write(f"  ✅ SimpleRCON réussi: {response[:50]}...")
            return True
            
        except Exception as e:
            self.stdout.write(f"  ❌ SimpleRCON échoué: {e}")
            return False

    def test_network_latency(self, host, port, iterations=5):
        """Test de latence réseau"""
        latencies = []
        
        for i in range(iterations):
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                result = sock.connect_ex((host, port))
                latency = (time.time() - start_time) * 1000
                sock.close()
                
                if result == 0:
                    latencies.append(latency)
                    self.stdout.write(f"  Test {i+1}: ✅ {latency:.2f}ms")
                else:
                    self.stdout.write(f"  Test {i+1}: ❌ Connexion échouée")
                
                time.sleep(0.5)
            except Exception as e:
                self.stdout.write(f"  Test {i+1}: ❌ {e}")
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            self.stdout.write(f"📊 Latence moyenne: {avg_latency:.2f}ms")
            return avg_latency < 1000
        return False

    def test_reliability_new(self, iterations):
        """Test de fiabilité avec la nouvelle implémentation"""
        success_count = 0
        
        for i in range(iterations):
            try:
                from minecraft_app.minecraft_service import test_rcon_connection
                if test_rcon_connection():
                    success_count += 1
                
                if (i + 1) % 2 == 0:
                    self.stdout.write(f"  Progression: {i+1}/{iterations} (✅ {success_count})")
                
                time.sleep(1)  # Délai entre tests
            except Exception as e:
                self.stdout.write(f"  Erreur test {i+1}: {e}")
        
        percentage = (success_count / iterations) * 100
        self.stdout.write(f"📊 Fiabilité: {success_count}/{iterations} ({percentage:.1f}%)")
        return percentage >= 80

    def show_recommendations(self, tests_results):
        """Affiche les recommandations"""
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("🔧 RECOMMANDATIONS")
        self.stdout.write("=" * 60)
        
        rcon_working = any(result[1] for result in tests_results[1:3])  # RCON tests
        
        if rcon_working:
            self.stdout.write(self.style.SUCCESS("🎉 RCON fonctionne avec la nouvelle implémentation !"))
            self.stdout.write("")
            self.stdout.write("✅ Votre problème est résolu. La nouvelle implémentation RCON fonctionne.")
            self.stdout.write("✅ Vous pouvez maintenant utiliser la boutique sans problème.")
        else:
            self.stdout.write("❌ RCON ne fonctionne pas encore. Vérifications supplémentaires:")
            self.stdout.write("")
            self.stdout.write("1. Vérifiez que le serveur Minecraft a RCON activé:")
            self.stdout.write("   enable-rcon=true")
            self.stdout.write("   rcon.port=30011")
            self.stdout.write("   rcon.password=JKL159-cPPp,;?")
            self.stdout.write("")
            self.stdout.write("2. Vérifiez les logs du serveur Minecraft")
            self.stdout.write("3. Testez la connexion RCON depuis un autre outil")