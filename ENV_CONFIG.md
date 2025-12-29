# Environment Configuration

## DEV (Local Development)
File `.env` - Azure SQL:
```env
DEBUG=true
SECRET_KEY=dev-secret-key
DB_ENGINE=mssql
DB_HOST=dacntt-sql-server.database.windows.net
DB_PORT=1433
DB_NAME=CSDL_TKB
DB_USERNAME=scheduling_user@dacntt-sql-server
DB_PASS=Admin123
```

## PROD (Azure App Service)
Azure Portal → Configuration → Application settings:
```
DEBUG=false
SECRET_KEY=prod-secret-key-random-strong
DB_ENGINE=mssql
DB_HOST=dacntt-sql-server.database.windows.net
DB_PORT=1433
DB_NAME=CSDL_TKB
DB_USERNAME=scheduling_user@dacntt-sql-server
DB_PASS=Admin123
DB_DRIVER=ODBC Driver 18 for SQL Server
ALLOWED_HOSTS=scheduling-web.azurewebsites.net
DISABLE_COLLECTSTATIC=true
ENABLE_ORYX_BUILD=true
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

## Firewall Setup
Azure Portal → SQL Server → Networking → Firewall rules:
- ✅ Allow Azure services and resources to access this server = ON
- Add your DEV IP: `103.249.23.127`
