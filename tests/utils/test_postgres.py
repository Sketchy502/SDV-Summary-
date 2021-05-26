import pytest
from sdv.utils.postgres import get_db_connection_string

class TestGetDBConnectionString:

    def test_empty_raises_exception(self):
        with pytest.raises(KeyError):
            get_db_connection_string({})

    def test_db_name_and_user(self):
        assert get_db_connection_string(dict(
            DB_NAME="mydb",
            DB_USER="myusr",
        )) == "dbname=mydb user=myusr"

    def test_db_name_user_password(self):
        assert get_db_connection_string(dict(
            DB_NAME="mydb",
            DB_USER="myusr",
            DB_PASSWORD="mypass",
        )) == "dbname=mydb user=myusr password=mypass"

    def test_all_attributes(self):
        assert get_db_connection_string(dict(
            DB_HOST="thehost",
            DB_NAME="mydb",
            DB_USER="myusr",
            DB_PASSWORD="mypass",
        )) == "dbname=mydb user=myusr password=mypass host=thehost"

