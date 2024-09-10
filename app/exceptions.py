class CustomException(Exception):
    def __init__(self, code: int, status_code: int, detail: str) -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail