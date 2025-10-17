"""
Configuration Helper - Access Django settings easily
Migrated and enhanced from src/config.py
"""

from django.conf import settings


class Config:
    """Centralized config access (backward compatible với src/config.py)"""
    
    class Database:
        """Database configuration"""
        
        @staticmethod
        def get_connection_string():
            """
            Get SQLAlchemy connection string for external libraries
            (Most Django code should use Django ORM instead)
            """
            db_config = settings.DATABASES['default']
            
            if db_config['ENGINE'] == 'mssql':
                username = db_config.get('USER', '')
                password = db_config.get('PASSWORD', '')
                host = db_config.get('HOST', '')
                name = db_config.get('NAME', '')
                
                if settings.DB_USE_WINDOWS_AUTH:
                    # Windows Authentication
                    return (
                        f"mssql+pyodbc://@{host}/"
                        f"{name}?driver=ODBC+Driver+17+for+SQL+Server&"
                        f"trusted_connection=yes"
                    )
                else:
                    # SQL Server Authentication
                    return (
                        f"mssql+pyodbc://{username}:{password}@{host}/"
                        f"{name}?driver=ODBC+Driver+17+for+SQL+Server"
                    )
            
            return None
        
        @staticmethod
        def get_engine():
            """Get database engine name"""
            return settings.DATABASES['default']['ENGINE']
        
        @staticmethod
        def get_name():
            """Get database name"""
            return settings.DATABASES['default']['NAME']
    
    class AI:
        """AI configuration"""
        
        @staticmethod
        def get_api_key():
            """Get Gemini API key"""
            return settings.GEMINI_API_KEY
        
        @staticmethod
        def get_model_name():
            """Get AI model name"""
            return settings.AI_MODEL_NAME
        
        @staticmethod
        def get_temperature():
            """Get AI temperature"""
            return settings.AI_TEMPERATURE
        
        @staticmethod
        def get_max_output_tokens():
            """Get max output tokens"""
            return settings.AI_MAX_OUTPUT_TOKENS
    
    class System:
        """System configuration"""
        
        @staticmethod
        def get_log_level():
            """Get log level"""
            return settings.LOG_LEVEL
        
        @staticmethod
        def get_schedule_output_dir():
            """Get schedule output directory"""
            return settings.SCHEDULE_OUTPUT_DIR


# Backward compatibility - Class-based access như src/config.py
class DatabaseConfig:
    """Backward compatible với src/config.py"""
    
    @classmethod
    def get_connection_string(cls):
        return Config.Database.get_connection_string()


class AIConfig:
    """Backward compatible với src/config.py"""
    
    GEMINI_API_KEY = property(lambda self: Config.AI.get_api_key())
    MODEL_NAME = property(lambda self: Config.AI.get_model_name())
    TEMPERATURE = property(lambda self: Config.AI.get_temperature())
    MAX_OUTPUT_TOKENS = property(lambda self: Config.AI.get_max_output_tokens())


class SystemConfig:
    """Backward compatible với src/config.py"""
    
    LOG_LEVEL = property(lambda self: Config.System.get_log_level())
    SCHEDULE_OUTPUT_DIR = property(lambda self: Config.System.get_schedule_output_dir())
