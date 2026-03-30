import pymysql

pymysql.install_as_MySQLdb()

# Bypass MariaDB/MySQL version check since you are likely using XAMPP with 10.4.32
from django.db.backends.base.base import BaseDatabaseWrapper
BaseDatabaseWrapper.check_database_version_supported = lambda self: True

# Turn off RETURNING support for older MariaDB versions
from django.db.backends.mysql.features import DatabaseFeatures
DatabaseFeatures.can_return_columns_from_insert = property(lambda self: False)
DatabaseFeatures.can_return_rows_from_bulk_insert = property(lambda self: False)