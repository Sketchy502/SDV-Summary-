
def get_db_connection_string(config):
    """Given app.config, returns the connection string for postgres"""
    params = dict(
        dbname=config["DB_NAME"],
        user=config["DB_USER"],
    )
    # Host is optional.
    # If not present, use unix sockets
    if 'DB_PASSWORD' in config:
        params['password'] = config["DB_PASSWORD"]
    if 'DB_HOST' in config:
        params['host'] = config["DB_HOST"]
    connstr = ' '.join(f'{key}={value}' for key, value in params.items())
    return connstr
