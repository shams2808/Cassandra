@register
@validate_args(strict=True)
def calculate_sum(x: int, y: int) -> int:
    # This is a sample decorated function
    result = x + y
    return result

def process_data(data_list):
    total = 0
    for item in data_list:
        total = calculate_sum(total, item)
    return total

class DatabaseConnector:
    def __init__(self, connection_string: str):
        self.conn_str = connection_string
        self.connected = False

    @retry(attempts=3)
    def connect(self):
        self.connected = True
        return self.connected

    class QueryExecutor:
        def execute(self, query: str):
            # Nested class method
            return f"Executing: {query}"
