import time
import functools
import traceback
from automation.logger import setup_logger

class TestFailureException(Exception):
    """Custom exception raised when a test validation check fails."""
    pass

class TestRunner:
    """Orchestrates test suite execution and logs performance and retry actions."""
    def __init__(self, name="TestRunner", config_path="configs/config.json"):
        self.logger = setup_logger(name, config_path)
        self.config_path = config_path

    def test_case(self, name: str, description: str = "", retries: int = 1, backoff_seconds: float = 1.0):
        """Decorator to mark a function as an automated validation test case.

        Handles logging, timers, exception tracking, and custom retries.
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                self.logger.info(f"--- Starting Test: {name} ---")
                if description:
                    self.logger.info(f"Description: {description}")
                
                attempt = 0
                start_time = time.time()
                status = "FAILED"
                error_msg = ""
                
                while attempt < retries:
                    attempt += 1
                    try:
                        self.logger.info(f"Attempt {attempt}/{retries}...")
                        result = func(*args, **kwargs)
                        status = "PASSED"
                        self.logger.info(f"Test {name} PASSED on attempt {attempt}")
                        return result
                    except AssertionError as ae:
                        error_msg = f"Assertion failure: {ae}"
                        self.logger.warn(f"Assertion failed: {ae}")
                    except TestFailureException as tfe:
                        error_msg = f"Validation failure: {tfe}"
                        self.logger.warn(f"Validation failed: {tfe}")
                    except Exception as e:
                        error_msg = f"Unexpected error: {e}"
                        self.logger.error(f"Error during execution: {e}\n{traceback.format_exc()}")
                    
                    if attempt < retries:
                        self.logger.info(f"Retrying in {backoff_seconds}s...")
                        time.sleep(backoff_seconds)
                
                duration = time.time() - start_time
                self.logger.error(f"--- Test FAILED: {name} (Duration: {duration:.2f}s) ---")
                raise TestFailureException(f"Test '{name}' failed after {retries} attempts. Reason: {error_msg}")
            
            return wrapper
        return decorator

    def run_stage(self, stage_name: str, func, *args, **kwargs):
        """Runs a validation function as a named stage, timing its completion."""
        self.logger.info(f"Executing Stage: {stage_name}")
        start_time = time.time()
        try:
            res = func(*args, **kwargs)
            duration = time.time() - start_time
            self.logger.info(f"Stage '{stage_name}' completed successfully in {duration:.2f}s")
            return res
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Stage '{stage_name}' failed after {duration:.2f}s with error: {e}")
            raise e
