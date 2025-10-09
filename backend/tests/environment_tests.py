# tests/test_environment.py
"""
Environment configuration tests for myTravelAgent
These tests verify that all environment variables, settings, and configurations
are properly set for production deployment on Render.
"""

import os
import sys
from unittest import skipIf, skipUnless

from django.conf import settings
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings


class EnvironmentVariableTests(TestCase):
    """Test that all required environment variables are properly configured"""
    
    def test_secret_key_configuration(self):
        """Ensure SECRET_KEY is properly set and secure"""
        # Check it's not the default
        self.assertNotEqual(
            settings.SECRET_KEY,
            'your-current-secret-key',
            "SECRET_KEY must be changed from default value"
        )
        
        # Check minimum length for security
        self.assertGreaterEqual(
            len(settings.SECRET_KEY),
            50,
            "SECRET_KEY should be at least 50 characters for security"
        )
        
        # Check it doesn't contain common patterns
        common_patterns = ['secret', 'default', 'changeme', '123456', 'password']
        for pattern in common_patterns:
            self.assertNotIn(
                pattern.lower(),
                settings.SECRET_KEY.lower(),
                f"SECRET_KEY contains insecure pattern: {pattern}"
            )
    
    def test_debug_setting_for_environment(self):
        """Ensure DEBUG is False in production/staging"""
        env = os.environ.get('ENVIRONMENT', 'development')
        
        if env in ['production', 'staging']:
            self.assertFalse(
                settings.DEBUG,
                f"DEBUG must be False in {env} environment"
            )
        
        # Additional check using Render's environment variable
        if os.environ.get('RENDER'):
            self.assertFalse(
                settings.DEBUG,
                "DEBUG must be False when deployed on Render"
            )
    
    def test_allowed_hosts_configuration(self):
        """Ensure ALLOWED_HOSTS is properly configured for Render"""
        if not settings.DEBUG:
            self.assertGreater(
                len(settings.ALLOWED_HOSTS),
                0,
                "ALLOWED_HOSTS must be configured in production"
            )
            
            # Check for Render domain
            self.assertTrue(
                any('.onrender.com' in host for host in settings.ALLOWED_HOSTS),
                "ALLOWED_HOSTS should include .onrender.com for Render deployment"
            )
            
            # Ensure no wildcards in production
            self.assertNotIn(
                '*',
                settings.ALLOWED_HOSTS,
                "ALLOWED_HOSTS should not use wildcard (*) in production"
            )
    
    def test_database_url_configuration(self):
        """Test DATABASE_URL is properly configured for Render PostgreSQL"""
        if os.environ.get('DATABASE_URL'):
            db_config = settings.DATABASES['default']
            
            # Should be using PostgreSQL
            self.assertEqual(
                db_config['ENGINE'],
                'django.db.backends.postgresql',
                "Must use PostgreSQL in production"
            )
            
            # Should not be using default values
            self.assertNotEqual(
                db_config['NAME'],
                'please-set-db-name',
                "Database name must be properly configured"
            )
            
            self.assertNotEqual(
                db_config['USER'],
                'please-set-db-user',
                "Database user must be properly configured"
            )
    
    def test_gemini_api_configuration(self):
        """Test Google Gemini API key is configured"""
        gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        
        if not settings.DEBUG:
            self.assertIsNotNone(
                gemini_key,
                "Gemini API key must be set for recommendation engine"
            )
            
            # Basic validation of key format
            if gemini_key:
                self.assertGreater(
                    len(gemini_key),
                    20,
                    "Gemini API key seems too short"
                )
                
                # Check it's not a placeholder
                placeholder_patterns = ['your-api-key', 'xxx', 'change-me', 'todo']
                for pattern in placeholder_patterns:
                    self.assertNotIn(
                        pattern.lower(),
                        gemini_key.lower(),
                        f"Gemini API key appears to be a placeholder: {pattern}"
                    )
    
    def test_required_environment_variables(self):
        """Test all required environment variables are set"""
        required_vars = []
        
        # Add required vars based on environment
        if not settings.DEBUG:
            required_vars.extend([
                'DATABASE_URL',
                'SECRET_KEY',
            ])
        
        if os.environ.get('RENDER'):
            required_vars.extend([
                'RENDER',
                'RENDER_SERVICE_NAME',
            ])
        
        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        self.assertEqual(
            len(missing_vars),
            0,
            f"Missing required environment variables: {missing_vars}"
        )


class DatabaseConfigurationTests(TransactionTestCase):
    """Test database configuration and connectivity for Render PostgreSQL"""
    
    def test_database_connection(self):
        """Test that database is accessible"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                self.assertEqual(result[0], 1, "Database connection test failed")
        except Exception as e:
            self.fail(f"Cannot connect to database: {e}")
    
    def test_database_is_postgresql(self):
        """Ensure we're using PostgreSQL (not SQLite)"""
        engine = settings.DATABASES['default']['ENGINE']
        self.assertEqual(
            engine,
            'django.db.backends.postgresql',
            f"Must use PostgreSQL, not {engine}"
        )
        
        # Double-check by querying database
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0].lower()
            self.assertIn('postgresql', version, "Database must be PostgreSQL")
    
    def test_postgresql_version(self):
        """Ensure PostgreSQL version is compatible with Render"""
        if 'postgresql' in settings.DATABASES['default']['ENGINE']:
            with connection.cursor() as cursor:
                cursor.execute("SHOW server_version")
                version_str = cursor.fetchone()[0]
                major_version = int(version_str.split('.')[0])
                
                # Render typically uses PostgreSQL 14+
                self.assertGreaterEqual(
                    major_version,
                    13,
                    f"PostgreSQL version {major_version} might be too old for Render (recommend 14+)"
                )
    
    def test_database_migrations_applied(self):
        """Ensure all migrations have been applied"""
        from io import StringIO

        from django.core.management import call_command
        
        out = StringIO()
        call_command('showmigrations', '--list', stdout=out)
        output = out.getvalue()
        
        # Check for unapplied migrations (would show [ ] instead of [X])
        unapplied = []
        for line in output.split('\n'):
            if '[ ]' in line:
                unapplied.append(line.strip())
        
        self.assertEqual(
            len(unapplied),
            0,
            f"Found unapplied migrations: {', '.join(unapplied)}"
        )
    
    def test_database_tables_exist(self):
        """Test that all expected tables exist"""
        expected_tables = [
            'auth_user',
            'api_trip',
            'api_destination', 
            'api_userpreferences',
            'api_planningsession',
            'destination_search_tripconversation',
            'destination_search_message',
            'destination_search_recommendations',
            'destination_search_conversationstate',
        ]
        
        with connection.cursor() as cursor:
            # PostgreSQL specific query
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = []
            for table in expected_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            self.assertEqual(
                len(missing_tables),
                0,
                f"Missing required tables: {missing_tables}"
            )


class RenderDeploymentTests(TestCase):
    """Tests specific to Render deployment configuration"""
    
    @skipUnless(os.environ.get('RENDER'), "Only run on Render")
    def test_render_environment_variables(self):
        """Test Render-specific environment variables are set"""
        render_vars = {
            'RENDER': 'Should be set to true on Render',
            'RENDER_SERVICE_NAME': 'Service name should be set',
            'RENDER_SERVICE_TYPE': 'Service type (web, pserv, etc)',
        }
        
        for var, description in render_vars.items():
            value = os.environ.get(var)
            self.assertIsNotNone(
                value,
                f"Render environment variable {var} not found: {description}"
            )
    
    def test_static_files_configuration(self):
        """Test static files are configured for Render"""
        # Check STATIC_URL is set
        self.assertEqual(
            settings.STATIC_URL,
            'static/',
            "STATIC_URL should be 'static/'"
        )
        
        # Check STATIC_ROOT is configured
        self.assertTrue(
            str(settings.STATIC_ROOT).endswith('staticfiles'),
            f"STATIC_ROOT should end with 'staticfiles', got: {settings.STATIC_ROOT}"
        )
        
        # Check WhiteNoise is in middleware
        self.assertIn(
            'whitenoise.middleware.WhiteNoiseMiddleware',
            settings.MIDDLEWARE,
            "WhiteNoise middleware must be installed for serving static files on Render"
        )
        
        # Check WhiteNoise is after SecurityMiddleware
        middleware_list = list(settings.MIDDLEWARE)
        security_index = middleware_list.index('django.middleware.security.SecurityMiddleware')
        whitenoise_index = middleware_list.index('whitenoise.middleware.WhiteNoiseMiddleware')
        
        self.assertGreater(
            whitenoise_index,
            security_index,
            "WhiteNoise must come after SecurityMiddleware"
        )
    
    @skipIf(settings.DEBUG, "Only test in production")
    def test_collectstatic_has_run(self):
        """Test that collectstatic has been run"""
        import os
        
        static_root = settings.STATIC_ROOT
        if os.path.exists(static_root):
            # Check for admin static files as indicator
            admin_css = os.path.join(static_root, 'admin', 'css', 'base.css')
            self.assertTrue(
                os.path.exists(admin_css),
                "Static files not collected. Run: python manage.py collectstatic --noinput"
            )
            
            # Check that staticfiles directory is not empty
            files_count = sum([len(files) for _, _, files in os.walk(static_root)])
            self.assertGreater(
                files_count,
                10,
                f"Static files directory seems empty (only {files_count} files)"
            )


class SecurityConfigurationTests(TestCase):
    """Test security settings for production deployment"""
    
    def test_cors_configuration(self):
        """Test CORS is properly configured"""
        # Check CORS settings exist
        self.assertFalse(
            settings.CORS_ALLOW_ALL_ORIGINS,
            "CORS_ALLOW_ALL_ORIGINS must be False (it's a security risk)"
        )
        
        if not settings.DEBUG:
            # Production should have specific allowed origins
            self.assertIn(
                'https://my-travel-agent.onrender.com',
                settings.CORS_ALLOWED_ORIGINS,
                "Production frontend URL should be in CORS_ALLOWED_ORIGINS"
            )
        else:
            # Development should allow localhost
            self.assertIn(
                'http://localhost:5173',
                settings.CORS_ALLOWED_ORIGINS,
                "Development should allow localhost:5173"
            )
        
        # Credentials should be allowed for JWT auth
        self.assertTrue(
            settings.CORS_ALLOW_CREDENTIALS,
            "CORS_ALLOW_CREDENTIALS must be True for JWT authentication"
        )
    
    def test_security_middleware(self):
        """Test security middleware is properly configured"""
        required_middleware = [
            'django.middleware.security.SecurityMiddleware',
            'corsheaders.middleware.CorsMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.middleware.clickjacking.XFrameOptionsMiddleware',
        ]
        
        missing_middleware = []
        for middleware in required_middleware:
            if middleware not in settings.MIDDLEWARE:
                missing_middleware.append(middleware)
        
        self.assertEqual(
            len(missing_middleware),
            0,
            f"Missing required middleware: {missing_middleware}"
        )
        
        # Check CORS middleware is at the top
        self.assertEqual(
            settings.MIDDLEWARE[0],
            'corsheaders.middleware.CorsMiddleware',
            "CORS middleware must be first in the middleware chain"
        )
    
    @skipIf(settings.DEBUG, "Only test in production")
    def test_production_security_settings(self):
        """Test production-specific security settings"""
        # These should be considered for production
        recommended_settings = {
            'SECURE_SSL_REDIRECT': 'Force HTTPS',
            'SESSION_COOKIE_SECURE': 'Secure session cookies',
            'CSRF_COOKIE_SECURE': 'Secure CSRF cookies',
            'SECURE_BROWSER_XSS_FILTER': 'Enable XSS filter',
            'SECURE_CONTENT_TYPE_NOSNIFF': 'Prevent content type sniffing',
            'X_FRAME_OPTIONS': 'Prevent clickjacking',
        }
        
        warnings = []
        for setting, description in recommended_settings.items():
            if not getattr(settings, setting, None):
                warnings.append(f"{setting}: {description}")
        
        if warnings:
            print("\nSecurity recommendations for production:")
            for warning in warnings:
                print(f"  - {warning}")
    
    def test_jwt_configuration(self):
        """Test JWT authentication is properly configured"""
        from datetime import timedelta

        # Check REST framework uses JWT
        self.assertIn(
            'rest_framework_simplejwt.authentication.JWTAuthentication',
            settings.REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'],
            "JWT authentication must be configured"
        )
        
        # Check JWT settings
        jwt_settings = settings.SIMPLE_JWT
        
        # Verify token lifetimes
        self.assertEqual(
            jwt_settings['ACCESS_TOKEN_LIFETIME'],
            timedelta(minutes=30),
            "Access token lifetime should be 30 minutes"
        )
        
        self.assertEqual(
            jwt_settings['REFRESH_TOKEN_LIFETIME'],
            timedelta(days=1),
            "Refresh token lifetime should be 1 day"
        )
        
        # In production, should have more secure settings
        if not settings.DEBUG:
            self.assertTrue(
                jwt_settings.get('ROTATE_REFRESH_TOKENS', False),
                "Should rotate refresh tokens in production"
            )


class PythonDependencyTests(TestCase):
    """Test Python and package versions meet requirements"""
    
    def test_python_version(self):
        """Test Python version meets minimum requirements"""
        min_version = (3, 9)
        current_version = sys.version_info[:2]
        
        self.assertGreaterEqual(
            current_version,
            min_version,
            f"Python {sys.version} is too old. Minimum required: {min_version[0]}.{min_version[1]}"
        )
        
        # Warn if using very old Python
        if current_version < (3, 10):
            print(f"\nWarning: Python {sys.version} is getting old. Consider upgrading to 3.11+")
    
    def test_django_version(self):
        """Test Django version is compatible"""
        import django
        
        django_version = tuple(map(int, django.__version__.split('.')[:2]))
        min_version = (4, 2)
        
        self.assertGreaterEqual(
            django_version,
            min_version,
            f"Django {django.__version__} is too old. Minimum required: {min_version[0]}.{min_version[1]}"
        )
    
    def test_critical_packages_installed(self):
        """Test all critical packages are installed"""
        import importlib
        
        critical_packages = {
            'rest_framework': 'djangorestframework',
            'corsheaders': 'django-cors-headers',
            'django_filters': 'django-filter',
            'whitenoise': 'whitenoise',
            'psycopg2': 'psycopg2-binary or psycopg2',
            'jwt': 'PyJWT',
            'dj_database_url': 'dj-database-url',
        }
        
        missing_packages = []
        for import_name, package_name in critical_packages.items():
            try:
                importlib.import_module(import_name)
            except ImportError:
                missing_packages.append(package_name)
        
        self.assertEqual(
            len(missing_packages),
            0,
            f"Missing critical packages: {missing_packages}. Install with: pip install {' '.join(missing_packages)}"
        )
    

class LoggingConfigurationTests(TestCase):
    """Test logging is properly configured for debugging issues"""
    
    def test_logging_configured(self):
        """Test Django logging is configured"""
        self.assertTrue(
            hasattr(settings, 'LOGGING'),
            "LOGGING configuration should be defined"
        )
        
        if not settings.DEBUG and hasattr(settings, 'LOGGING'):
            logging_config = settings.LOGGING
            
            # Should have handlers configured
            self.assertIn('handlers', logging_config)
            
            # Should have django handler for errors
            if 'loggers' in logging_config:
                self.assertIn(
                    'django',
                    logging_config['loggers'],
                    "Should have Django logger configured"
                )
    
    @skipIf(settings.DEBUG, "Only relevant in production")
    def test_error_tracking_configured(self):
        """Test error tracking (Sentry/Rollbar) is configured for production"""
        # Check for Sentry
        sentry_dsn = os.environ.get('SENTRY_DSN')
        
        # Check for other error tracking services
        rollbar_token = os.environ.get('ROLLBAR_ACCESS_TOKEN')
        
        if not (sentry_dsn or rollbar_token):
            print("\nWarning: No error tracking service configured (Sentry/Rollbar recommended)")


class DeploymentChecklistTests(TestCase):
    """Final deployment checklist tests"""
    
    def test_no_todo_comments(self):
        """Check for TODO comments that shouldn't be in production"""
        import os
        
        if not settings.DEBUG:
            todos_found = []
            
            # Check main app directories
            for app_dir in ['api', 'destination_search', 'backend']:
                if not os.path.exists(app_dir):
                    continue
                    
                for root, dirs, files in os.walk(app_dir):
                    # Skip migrations and test files
                    if 'migrations' in root or 'test' in root:
                        continue
                    
                    for file in files:
                        if file.endswith('.py'):
                            filepath = os.path.join(root, file)
                            with open(filepath, 'r') as f:
                                for i, line in enumerate(f, 1):
                                    if 'TODO' in line or 'FIXME' in line:
                                        todos_found.append(f"{filepath}:{i}")
            
            if todos_found:
                print(f"\nWarning: Found {len(todos_found)} TODO/FIXME comments in code")
    
    def test_requirements_file_complete(self):
        """Test requirements.txt exists and contains all necessary packages"""
        import os
        
        self.assertTrue(
            os.path.exists('requirements.txt'),
            "requirements.txt must exist for deployment"
        )
        
        with open('requirements.txt', 'r') as f:
            requirements = f.read().lower()
            
            essential_packages = [
                'django',
                'djangorestframework',
                'django-cors-headers',
                'psycopg2',
                'whitenoise',
                'gunicorn',  # For Render deployment
                'dj-database-url',
                'python-dotenv',
                'google-generativeai',  # For Gemini API
            ]
            
            missing = []
            for package in essential_packages:
                if package not in requirements:
                    missing.append(package)
            
            if missing:
                self.fail(f"Missing essential packages in requirements.txt: {missing}")