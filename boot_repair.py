import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import subprocess
import asyncio
import psutil
import threading
import ast
from typing import Dict, Any
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import pandas as pd
from dotenv import load_dotenv
from pyvirtualdisplay import Display
import atexit

# If you want local LLM usage:
from transformers import AutoTokenizer
try:
    from vllm import LLM, SamplingParams
except Exception:
    LLM = None
    SamplingParams = None

# 3rd-party LLM API (DeepSeek or OpenAI):
from openai import OpenAI
import time

# -------------------------------------------------------------------
# WARNING: This code is a simplified demonstration of patch-based
# self-modification. Use in a sandbox environment only!
# -------------------------------------------------------------------

# -------------------- ENV & PATHS --------------------
load_dotenv()
THIS_FILE_PATH = Path(__file__).resolve()
LOGS_DIR = THIS_FILE_PATH.parent / "logs"
DATA_DIR = THIS_FILE_PATH.parent / "data"
MODELS_DIR = THIS_FILE_PATH.parent / "models"


def ensure_directories_exist():
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Failed to create directories: {e}", file=sys.stderr)


ensure_directories_exist()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "REPLACE_ME")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ----------- GLOBAL LOGGING CONFIG -----------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        TimedRotatingFileHandler(
            LOGS_DIR / "repair_log.txt",
            when="midnight",
            backupCount=7
        )
    ]
)
logger = logging.getLogger("boot_repair_automation")
logger.debug("Logger initialized successfully.")

# Start a virtual display if no DISPLAY environment variable is present
display = None

def _stop_virtual_display():
    if display:
        try:
            display.stop()
            logger.debug("Stopped virtual X display.")
        except Exception as e:
            logger.warning(f"Failed to stop virtual display: {e}")

if not os.environ.get("DISPLAY"):
    try:
        display = Display()
        display.start()
        logger.debug("Started virtual X display for headless environment.")
        atexit.register(_stop_virtual_display)
    except Exception as e:
        logger.warning(f"Failed to start virtual display: {e}")

# -------------- LLM / DEEPSEEK SETUP --------------
try:
    if LLM is not None:
        tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-V2.5")
        llm = LLM(
            model="deepseek-ai/DeepSeek-V2.5",
            tensor_parallel_size=1,
            max_model_len=8192,
            trust_remote_code=True,
            enforce_eager=True,
            device="cpu"
        )
        sampling_params = SamplingParams(
            temperature=0.3,
            max_tokens=256,
            stop_token_ids=[tokenizer.eos_token_id],
        )
    else:
        raise RuntimeError("vLLM not available")
except Exception as e:
    logger.warning(f"vLLM local model not available: {e}")
    llm = None
    sampling_params = None

try:
    ds_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
except Exception as e:
    logger.warning(f"Failed to initialize DeepSeek client: {e}")
    ds_client = None


def query_deepseek(prompt: str) -> str:
    """
    Ask the LLM (DeepSeek or fallback) for a response.
    """
    if ds_client is not None:
        try:
            response = ds_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an autonomous repair assistant "
                            "that returns patches (diff)."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            if response and response.choices:
                return response.choices[0].message.content
            else:
                logger.error("Empty or invalid response from DeepSeek API.")
                return "I couldn't process your request. Please try again."
        except Exception as e:
            logger.error(f"Failed to query DeepSeek API: {e}")
            return "I couldn't process your request. Please try again."
    else:
        logger.warning("No DeepSeek client. Returning placeholder.")
        return "No LLM is configured. (Placeholder response)."

# --------------------------------------------------------------------------
#    PATCH-BASED SELF-MODIFICATION LOGIC
# --------------------------------------------------------------------------


def propose_patch_changes(user_instructions: str, error_info: str = "") -> str:
    """
    Get a *diff/patch* (not entire code) from the LLM, describing what lines
    to add/remove. We'll apply it to the existing file if valid.
    """
    try:
        with open(THIS_FILE_PATH, "r", encoding="utf-8") as f:
            current_code = f.read()
    except Exception as e:
        logger.error(f"Failed to read script: {e}")
        return ""

    prompt = (
        "You are the code for this entire file. "
        "The user wants incremental changes.\n"
        "Provide a unified diff patch (like what 'diff -u' produces) that "
        "modifies only the relevant lines.\n"
        "If no changes are needed, return an empty diff.\n\n"
        f"User instructions:\n{user_instructions}\n\n"
        f"Error info:\n{error_info}\n\n"
        "Here is the current code:\n"
        f"{current_code}"
    )

    diff_text = query_deepseek(prompt)
    return diff_text


def apply_patch_changes(diff_text: str) -> str:
    """
    Parse a unified diff in diff_text, apply it to the current file in memory,
    and write the result to a temp file for testing. If tests pass, finalize.
    """
    if not diff_text.strip():
        logger.info("No diff returned. No changes made.")
        return "No changes proposed."

    # Read the current code lines
    try:
        with open(THIS_FILE_PATH, "r", encoding="utf-8") as f:
            original_lines = f.readlines()
    except Exception as e:
        msg = f"Failed to read original file lines: {e}"
        logger.error(msg)
        return msg

    # Parse the diff
    patched_lines = []
    try:

        patch_path = THIS_FILE_PATH.parent / "temp.patch"
        with open(patch_path, "w", encoding="utf-8") as pf:
            pf.write(diff_text)

        original_temp = THIS_FILE_PATH.parent / "original_temp.py"
        with open(original_temp, "w", encoding="utf-8") as of:
            of.writelines(original_lines)

        patched_temp = THIS_FILE_PATH.parent / "patched_temp.py"
        patch_cmd = ["patch", str(original_temp), str(
            patch_path), "-o", str(patched_temp)]
        proc = subprocess.run(patch_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            msg = f"Patch command failed: {proc.stderr}"
            logger.error(msg)
            patch_path.unlink(missing_ok=True)
            original_temp.unlink(missing_ok=True)
            return msg

        with open(patched_temp, "r", encoding="utf-8") as pf:
            patched_lines = pf.readlines()

        patch_path.unlink(missing_ok=True)
        original_temp.unlink(missing_ok=True)
        patched_temp.unlink(missing_ok=True)

    except Exception as e:
        msg = f"Failed to apply patch: {e}"
        logger.error(msg)
        return msg

    new_code = "".join(patched_lines)

    try:
        ast.parse(new_code)
    except SyntaxError as e:
        msg = f"Patched code has syntax errors: {e}"
        logger.error(msg)
        return msg

    test_result = run_local_test_suite_with_code(new_code)
    if not test_result["passed"]:
        msg = f"Test suite failed after patch: {test_result['reason']}"
        logger.error(msg)
        return msg

    backup_path = THIS_FILE_PATH.parent / f"{THIS_FILE_PATH.stem}_backup.py"
    try:
        with open(THIS_FILE_PATH, "r", encoding="utf-8") as oldf:
            old_code = oldf.read()
        with open(backup_path, "w", encoding="utf-8") as bf:
            bf.write(old_code)

        with open(THIS_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(new_code)

        logger.info("Patch applied successfully!")
        attempt_git_commit("Applied patch-based code updates.")
        return f"Code updated successfully via patch. Backup at {backup_path}"
    except Exception as e:
        msg = f"Failed to write final patched code: {e}"
        logger.error(msg)
        return msg


def run_local_test_suite_with_code(new_code: str) -> Dict[str, Any]:
    """
    Minimal approach: write the code to a temp file with `--testmode`
    to see if it starts up.
    """
    temp_path = THIS_FILE_PATH.parent / "temp_patch_test.py"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(new_code)
    except Exception as e:
        return {"passed": False, "reason": f"Cannot write temp code: {e}"}

    try:
        result = subprocess.run(
            [sys.executable, str(temp_path), "--testmode"],
            capture_output=True,
            text=True,
            timeout=10
        )
        temp_path.unlink(missing_ok=True)
        if result.returncode != 0:
            reason = (
                f"Exit code {result.returncode}\n"
                f"Stdout:\n{result.stdout}\n"
                f"Stderr:\n{result.stderr}"
            )
            return {"passed": False, "reason": reason}
        return {"passed": True, "reason": "All good."}
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        return {"passed": False, "reason": f"Test run exception: {e}"}


def attempt_git_commit(commit_msg: str):
    logger.info("Attempting Git commit for patch changes...")
    try:
        subprocess.run(["git", "add", str(THIS_FILE_PATH)], check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        logger.info("Git commit successful.")
    except Exception as e:
        logger.warning(f"Git commit failed or git not installed: {e}")


def patch_self_modify(user_instructions: str, error_info: str = "") -> str:
    """
    High-level function: ask for a patch, then apply it if valid.
    """
    diff_text = propose_patch_changes(user_instructions, error_info)
    if not diff_text.strip():
        return "No patch proposed by LLM."
    return apply_patch_changes(diff_text)

# A simpler "apply_solution" that uses patches


def apply_solution(solution: str) -> bool:
    """
    If the 'solution' is a diff, we apply it. If it's not, we treat it as
    instructions to produce a diff.
    """
    logger.info("Applying solution in a patch-based manner.")
    if solution.startswith("--- "):
        result = apply_patch_changes(solution)
        return "Code updated successfully" in result
    else:
        result = patch_self_modify(solution)
        return "Code updated successfully" in result


class BootRepairUI:
    def __init__(self, agent):
        self.agent = agent
        self.root = tk.Tk()
        self.root.title("Patch-based Boot Repair UI")
        self.root.geometry("400x200")

        self.status_label = tk.Label(
            self.root, text="Status: Idle", font=("Arial", 12))
        self.status_label.pack(pady=10)

        self.repair_button = ttk.Button(
            self.root, text="Start Boot Repair", command=self.start_repair)
        self.repair_button.pack(pady=10)

    def run(self):
        self.root.mainloop()

    def start_repair(self):
        self.status_label.config(text="Status: Running boot repair...")
        asyncio.create_task(self._run_repair_async())

    async def _run_repair_async(self):
        success = await self.agent.run_boot_repair()
        if success:
            self.status_label.config(text="Status: Repair completed.")
        else:
            self.status_label.config(
                text="Status: Repair failed or incomplete.")


class BootIssuePredictor:
    def __init__(self):
        self.logger = logging.getLogger("boot_issue_predictor")
        self.model = RandomForestClassifier(random_state=42)
        self.data_path = DATA_DIR / "synthetic_boot_issues.csv"
        self.issue_mapping = {
            "kernel_panic_rootfs": "kernel_panic_rootfs",
            "filesystem_corrupt": "filesystem_corrupt",
            "grub_device_error": "grub_device_error",
            "no_issue": "no_issue"
        }
        self.load_and_train_model()

    def load_and_train_model(self):
        data = self.load_data(self.data_path)
        if not data.empty:
            self.train_model(data)
        else:
            self.logger.warning("No data available to train the model.")

    def load_data(self, csv_path: Path) -> pd.DataFrame:
        if not csv_path.exists():
            self.logger.warning(f"Data file {csv_path} does not exist.")
            return pd.DataFrame()
        try:
            data = pd.read_csv(csv_path)
            data['issue'] = data['issue'].map(
                self.issue_mapping).fillna("unknown")
            data['efi_mounted'] = data['efi_mounted'].astype(int)
            return data
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return pd.DataFrame()

    def train_model(self, data: pd.DataFrame):
        try:
            if data.empty or len(data) < 5:
                self.logger.warning("Insufficient training data.")
                return
            X = data.drop(columns=['issue'])
            y = data['issue']
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42)
            self.model.fit(X_train, y_train)
            accuracy = self.model.score(X_test, y_test)
            self.logger.info(f"Model trained with accuracy: {accuracy:.2f}")
        except Exception as e:
            self.logger.error(f"Failed to train model: {e}")

    def predict_issue(self, system_state: Dict[str, Any]) -> str:
        try:
            if not hasattr(self.model, "feature_importances_"):
                self.logger.warning("Model is not fitted.")
                return "unknown"
            df = pd.DataFrame([system_state])
            if df.isnull().any().any():
                self.logger.warning("Invalid system state data.")
                return "unknown"
            return self.model.predict(df)[0]
        except Exception as e:
            self.logger.error(f"Failed to predict issue: {e}")
            return "unknown"


class BootRepairLogic:
    def __init__(self):
        self.logger = logging.getLogger("boot_repair_logic")
        self.current_process = None
        self.process_status = "idle"

    async def repair_issue(self, issue: str) -> bool:
        try:
            self.logger.info(f"Attempting to repair issue: {issue}")
            self.process_status = "running"
            if issue == "kernel_panic_rootfs":
                return await self._repair_kernel_panic_rootfs()
            elif issue == "filesystem_corrupt":
                return await self._repair_filesystem_corrupt()
            else:
                self.logger.warning(f"No direct logic for issue: {issue}")
                self.process_status = "failed"
                return False
        except Exception as e:
            self.logger.error(f"Failed to repair {issue}: {e}")
            self.process_status = "failed"
            error_details = f"Error in repair_issue: {e}"
            solution = query_deepseek(error_details)
            if apply_solution(solution):
                return await self.repair_issue(issue)
            return False

    async def _repair_kernel_panic_rootfs(self) -> bool:
        try:
            self.logger.info("Repairing kernel panic rootfs...")
            self.current_process = subprocess.Popen(
                ["mkinitcpio", "-P"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.current_process.wait()
            if self.current_process.returncode != 0:
                raise subprocess.CalledProcessError(
                    self.current_process.returncode, self.current_process.args)

            self.current_process = subprocess.Popen(
                ["grub-mkconfig", "-o", "/boot/grub/grub.cfg"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.current_process.wait()
            if self.current_process.returncode != 0:
                raise subprocess.CalledProcessError(
                    self.current_process.returncode, self.current_process.args)

            self.process_status = "completed"
            return True
        except subprocess.CalledProcessError as e:
            err_msg = (
                f"Command failed: {e.cmd}, "
                f"Output: {e.output}, Error: {e.stderr}"
            )
            self.logger.error(err_msg)
            self.process_status = "failed"
            solution = query_deepseek(err_msg)
            if apply_solution(solution):
                return await self._repair_kernel_panic_rootfs()
            return False
        except Exception as e:
            err_msg = f"Unexpected error: {e}"
            self.logger.error(err_msg)
            self.process_status = "failed"
            solution = query_deepseek(err_msg)
            if apply_solution(solution):
                return await self._repair_kernel_panic_rootfs()
            return False

    async def _repair_filesystem_corrupt(self) -> bool:
        self.logger.info("Repairing filesystem corruption (stub).")
        self.process_status = "completed"
        return True


class DefaultProcessManager:
    def terminate_all(self):
        logger.info("Terminating all processes... (Placeholder)")


class EnhancedAutomationManager:
    def __init__(self):
        self.logger = logging.getLogger("enhanced_automation_manager")
        self.boot_issue_predictor = BootIssuePredictor()
        self.boot_repair_logic = BootRepairLogic()
        self.ui = BootRepairUI(self)
        self.process_manager = DefaultProcessManager()

        self._initialize_ml_model()
        self._start_monitoring()

    def _initialize_ml_model(self):
        try:
            self.logger.info("Initializing ML model...")
            self.boot_issue_predictor.load_and_train_model()
        except Exception as e:
            self.logger.error(f"Failed to initialize ML: {e}")

    def _start_monitoring(self):
        self.logger.info("System monitoring started...")

    async def run_boot_repair(self) -> bool:
        try:
            self.logger.info("Running boot repair...")
            system_state = self._get_system_state()
            predicted_issue = self.boot_issue_predictor.predict_issue(
                system_state)
            self.logger.info(f"Predicted issue: {predicted_issue}")
            await self.log_system_state(predicted_issue)

            success = await self.boot_repair_logic.repair_issue(
                predicted_issue
            )
            if success:
                self.logger.info(f"Issue {predicted_issue} repaired!")
            else:
                self.logger.warning(
                    f"Could not repair issue: {predicted_issue}")
            return success
        except Exception as e:
            err_msg = f"run_boot_repair failed: {e}"
            self.logger.error(err_msg)
            solution = query_deepseek(err_msg)
            if apply_solution(solution):
                return await self.run_boot_repair()
            return False

    def _get_system_state(self) -> Dict[str, Any]:
        try:
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            disk_free_gb = psutil.disk_usage('/').free / (1024 ** 3)
            efi_mounted = os.path.exists('/boot/efi')
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_free_gb": disk_free_gb,
                "efi_mounted": efi_mounted
            }
        except Exception as e:
            self.logger.error(f"Failed to get system state: {e}")
            return {}

    async def log_system_state(self, issue: str):
        self.logger.info(f"System state logged for {issue}")


class ChatInterface:
    """
    A console-based interface supporting patch-based code changes.
    """
    def __init__(self, agent):
        self.agent = agent
        self.logger = logging.getLogger("chat_interface")

    async def start_chat(self):
        self.logger.info("Chat started. Type 'exit' to quit.")
        print(
            "Hello! I'm your patch-based autonomous boot repair assistant. "
            "How can I help you today?"
        )

        while True:
            user_input = input("You: ").strip()
            if user_input.lower() == "exit":
                print("Goodbye!")
                break

            response = await self.process_input(user_input)
            print(f"Agent: {response}")

    async def process_input(self, user_input: str) -> str:
        try:
            return await self._route_command(user_input)
        except Exception as e:
            self.logger.error(f"Error processing input: {e}")
            return "An error occurred. I'll attempt to fix it."

    async def _route_command(self, user_input: str) -> str:
        lower_input = user_input.lower()

        if "repair" in lower_input or "start" in lower_input:
            await self.agent.run_boot_repair()
            return "Initiated boot repair."
        elif "status" in lower_input or "state" in lower_input:
            state = self.agent._get_system_state()
            return (
                f"CPU: {state.get('cpu_percent')}%\n"
                f"Memory: {state.get('memory_percent')}%\n"
                f"Disk Free (GB): {state.get('disk_free_gb')}\n"
                f"EFI Mounted: {state.get('efi_mounted')}"
            )
        elif "terminate" in lower_input or "stop" in lower_input:
            self.agent.process_manager.terminate_all()
            return "Terminated all running processes."
        elif (
            "self modify" in lower_input
            or "update code" in lower_input
            or "patch code" in lower_input
        ):
            print("Enter instructions for patch-based code modification:")
            instructions = input("Instructions: ")
            return patch_self_modify(instructions)
        elif "error" in lower_input:
            return self._handle_error(user_input)
        elif "list" in lower_input or "help" in lower_input:
            return self.list_functions()
        else:
            prompt = (
                f"User said: '{user_input}'. Provide a patch or instructions "
                f"for patch-based updates if relevant."
            )
            solution = query_deepseek(prompt)
            if solution.startswith("--- "):
                result = apply_patch_changes(solution)
                return f"Patch result: {result}"
            else:
                result = patch_self_modify(solution)
                return result

    def list_functions(self) -> str:
        funcs = [
            "start_repair (or 'repair')",
            "stop_repair (terminate all)",
            "check_status (or 'status')",
            "patch code (self_modify / update code)",
            "list / help",
            "exit"
        ]
        return "Available functions:\n" + "\n".join(funcs)

    def _handle_error(self, error_str: str) -> str:
        self.logger.info(f"Handling an error: {error_str}")
        solution = query_deepseek(error_str)
        return patch_self_modify(solution, error_str)


def main():
    if "--testmode" in sys.argv:
        logger.info("Running in testmode, exit 0.")
        sys.exit(0)

    while True:
        try:
            automation_manager = EnhancedAutomationManager()

            chat_interface = ChatInterface(automation_manager)
            chat_thread = threading.Thread(
                target=asyncio.run, args=(chat_interface.start_chat(),))
            chat_thread.start()

            automation_manager.ui.run()
            break
        except Exception as e:
            logger.error(f"Fatal error in main: {e}")
            solution = query_deepseek(f"Fatal error: {e}")
            apply_solution(solution)
            logger.info("Retry in 5 sec...")
            time.sleep(5)


if __name__ == "__main__":
    main()
