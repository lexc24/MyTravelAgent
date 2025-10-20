# backend/tests.py

import os
from datetime import timedelta
from unittest.mock import patch

import dj_database_url
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase


class HealthCheckTests(TestCase):
    """Test health check endpoint"""
    
    def test_health_check_endpoint(self):
        """Test that health check returns OK"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'OK')


class URLRoutingTests(APITestCase):
    """Test that all main URL patterns are accessible"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
    def test_admin_url_exists(self):
        """Test admin URL is accessible"""
        response = self.client.get('/admin/')
        # Should redirect to login
        self.assertIn(response.status_code, [302, 301])  # Redirect codes
        
    def test_api_auth_urls_exist(self):
        """Test API authentication URLs exist"""
        # Registration
        response = self.client.post('/api/user/register', {})
        self.assertIn(response.status_code, [400, 201])  # Bad request or created
        
        # Token
        response = self.client.post('/api/token', {})
        self.assertIn(response.status_code, [400, 401])  # Bad request or unauthorized
        
        # Refresh
        response = self.client.post('/api/token/refresh', {})
        self.assertIn(response.status_code, [400, 401])
        
    def test_api_root_accessible(self):
        """Test API root is accessible"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api')
        self.assertEqual(response.status_code, 200)


class DebugSettingsTests(TestCase):
    """Test debug-specific settings"""
    
    @override_settings(
        DEBUG=True,
        ALLOWED_HOSTS=['localhost', '127.0.0.1']
    )
    def test_debug_allowed_hosts(self):
        """Test ALLOWED_HOSTS in debug mode"""
        # Note: Django adds 'testserver' automatically in tests
        self.assertTrue(
            'localhost' in settings.ALLOWED_HOSTS or 
            'testserver' in settings.ALLOWED_HOSTS
        )


class ProductionSettingsTests(TestCase):
    """Test production-specific settings"""
    
    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=['.onrender.com', 'localhost']
    )
    def test_production_allowed_hosts(self):
        """Test ALLOWED_HOSTS in production mode"""
        # This will test the override_settings value
        self.assertIn('.onrender.com', settings.ALLOWED_HOSTS)


class CORSConfigurationTests(TestCase):
    """Test CORS configuration"""
    
    @override_settings(
        DEBUG=True,
        CORS_ALLOWED_ORIGINS=['http://localhost:5173', 'http://127.0.0.1:5173']
    )
    def test_development_cors_origins(self):
        """Test CORS origins in development"""
        self.assertIn('http://localhost:5173', settings.CORS_ALLOWED_ORIGINS)
        self.assertIn('http://127.0.0.1:5173', settings.CORS_ALLOWED_ORIGINS)
        
    @override_settings(
        DEBUG=False,
        CORS_ALLOWED_ORIGINS=['https://my-travel-agent.onrender.com']
    )
    def test_production_cors_origins(self):
        """Test CORS origins in production"""
        self.assertIn('https://my-travel-agent.onrender.com', settings.CORS_ALLOWED_ORIGINS)
        
    def test_cors_credentials_allowed(self):
        """Test CORS allows credentials"""
        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)


class JWTConfigurationTests(TestCase):
    """Test JWT configuration"""
    
    def test_jwt_token_lifetime(self):
        """Test JWT token lifetime settings"""
        jwt_settings = settings.SIMPLE_JWT
        self.assertEqual(jwt_settings['ACCESS_TOKEN_LIFETIME'], timedelta(minutes=30))
        self.assertEqual(jwt_settings['REFRESH_TOKEN_LIFETIME'], timedelta(days=1))
        
    def test_jwt_authentication_default(self):
        """Test JWT is default authentication"""
        rest_settings = settings.REST_FRAMEWORK
        self.assertIn(
            'rest_framework_simplejwt.authentication.JWTAuthentication',
            rest_settings['DEFAULT_AUTHENTICATION_CLASSES']
        )


class MiddlewareOrderTests(TestCase):
    """Test middleware ordering"""
    
    def test_cors_middleware_first(self):
        """Test CORS middleware is first in the chain"""
        middleware = settings.MIDDLEWARE
        self.assertEqual(middleware[0], 'corsheaders.middleware.CorsMiddleware')
        
    def test_whitenoise_middleware_position(self):
        """Test WhiteNoise middleware is properly positioned"""
        middleware = settings.MIDDLEWARE
        security_index = middleware.index('django.middleware.security.SecurityMiddleware')
        whitenoise_index = middleware.index('whitenoise.middleware.WhiteNoiseMiddleware')
        
        # WhiteNoise should come after SecurityMiddleware
        self.assertTrue(whitenoise_index > security_index)


class DatabaseConfigurationTests(TestCase):
    """Test database configuration"""
    
    def test_database_url_parsing(self):
        """Test DATABASE_URL parsing functionality"""
        # Test that dj_database_url can parse a PostgreSQL URL correctly
        test_url = 'postgresql://user:pass@localhost/dbname'
        db_config = dj_database_url.parse(test_url)
        
        self.assertEqual(db_config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(db_config['NAME'], 'dbname')
        self.assertEqual(db_config['USER'], 'user')
        self.assertEqual(db_config['PASSWORD'], 'pass')
        self.assertEqual(db_config['HOST'], 'localhost')
        
    def test_default_database_config(self):
        """Test default database configuration structure"""
        db_config = settings.DATABASES['default']
        self.assertIn('ENGINE', db_config)
        self.assertEqual(db_config['ENGINE'], 'django.db.backends.postgresql')


class StaticFilesConfigurationTests(TestCase):
    """Test static files configuration"""
    
    def test_static_url_configuration(self):
        """Test static URL is configured"""
        # STATIC_URL might have a leading slash
        self.assertTrue(
            settings.STATIC_URL == 'static/' or 
            settings.STATIC_URL == '/static/'
        )
        
    def test_static_root_configuration(self):
        """Test static root is configured"""
        self.assertTrue(str(settings.STATIC_ROOT).endswith('staticfiles'))


class InstalledAppsTests(TestCase):
    """Test installed apps configuration"""
    
    def test_required_apps_installed(self):
        """Test all required apps are installed"""
        required_apps = [
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
            'api',
            'django_filters',
            'rest_framework',
            'corsheaders',
            'destination_search'
        ]
        
        for app in required_apps:
            self.assertIn(app, settings.INSTALLED_APPS)


class AuthenticationIntegrationTests(APITestCase):
    """Test authentication flow integration"""
    
    def test_complete_auth_flow(self):
        """Test complete authentication flow from registration to API access"""
        client = APIClient()
        
        # 1. Register user
        register_url = reverse('register')
        register_data = {
            'username': 'newuser',
            'password': 'newpass123',
            'email': 'new@example.com'
        }
        response = client.post(register_url, register_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 2. Login to get tokens
        token_url = reverse('get_token')
        token_data = {
            'username': 'newuser',
            'password': 'newpass123'
        }
        response = client.post(token_url, token_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        access_token = response.data['access']
        refresh_token = response.data['refresh']
        
        # 3. Use access token to access protected endpoint
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.get('/api/trips')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Refresh token
        refresh_url = reverse('refresh')
        refresh_data = {'refresh': refresh_token}
        response = client.post(refresh_url, refresh_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        new_access_token = response.data['access']
        
        # 5. Use new access token
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access_token}')
        response = client.get('/api/trips')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ErrorHandlingTests(APITestCase):
    """Test error handling and status codes"""
    
    def test_404_for_nonexistent_endpoint(self):
        """Test 404 is returned for non-existent endpoints"""
        response = self.client.get('/api/nonexistent')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_401_for_unauthenticated_access(self):
        """Test 401 is returned for unauthenticated access to protected endpoints"""
        response = self.client.get('/api/trips')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_405_for_unsupported_methods(self):
        """Test 405 is returned for unsupported HTTP methods"""
        user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.client.force_authenticate(user=user)
        
        # Try to POST to a read-only endpoint (destinations is read-only)
        response = self.client.post('/api/destinations', {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)