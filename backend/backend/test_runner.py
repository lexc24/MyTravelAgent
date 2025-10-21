# backend/test_runner.py
from django.test.runner import DiscoverRunner
from django.db import connections


class ForceCloseConnectionTestRunner(DiscoverRunner):
    """Custom test runner that forces database connections to close"""
    
    def teardown_databases(self, old_config, **kwargs):
        """
        Force close all database connections before destroying test databases.
        """
        # Force close all connections
        for alias in connections:
            try:
                connections[alias].close()
            except Exception:
                pass
        
        # Now destroy the databases
        super().teardown_databases(old_config, **kwargs)