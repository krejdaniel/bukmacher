from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


BACKEND = Path(__file__).resolve().parents[2] / "backend"
PYTHON = BACKEND / "venv" / "Scripts" / "python.exe"


class ProcessRunner(QObject):

    output = Signal(str)
    finished = Signal(int)

    def __init__(self):
        super().__init__()

        self.process = QProcess()

        self.process.setWorkingDirectory(str(BACKEND))

        self.process.readyReadStandardOutput.connect(
            self.read_stdout
        )

        self.process.readyReadStandardError.connect(
            self.read_stderr
        )

        self.process.finished.connect(
            self.on_finished
        )

        self.process.errorOccurred.connect(
            self.on_error
        )

    def is_running(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    def run_backtest(self):

        if self.is_running():
            self.output.emit(
                "\n>>> Proces już jest uruchomiony!\n"
            )
            return

        self.output.emit(
            "\n>>> Uruchamianie backtestu...\n"
        )

        self.output.emit(
            f">>> Python: {PYTHON}\n"
        )

        self.output.emit(
            f">>> Backend: {BACKEND}\n"
        )

        self.process.start(
            str(PYTHON),
            [
                "-m",
                "app.ml.backtest"
            ]
        )

    def run_predict(self):

        if self.is_running():
            self.output.emit(
                "\n>>> Proces już jest uruchomiony!\n"
            )
            return

        self.output.emit(
            "\n>>> Uruchamianie predict...\n"
        )

        self.output.emit(
            f">>> Python: {PYTHON}\n"
        )

        self.output.emit(
            f">>> Backend: {BACKEND}\n"
        )

        self.process.start(
            str(PYTHON),
            [
                "predict.py"
            ]
        )

    def read_stdout(self):

        text = bytes(
            self.process.readAllStandardOutput()
        ).decode(
            "utf-8",
            errors="ignore"
        )

        self.output.emit(text)

    def read_stderr(self):

        text = bytes(
            self.process.readAllStandardError()
        ).decode(
            "utf-8",
            errors="ignore"
        )

        self.output.emit(text)

    def on_error(self, error):

        self.output.emit(
            f"\n>>> QPROCESS ERROR: {error}\n"
        )

    def on_finished(self, code, status):

        self.output.emit(
            f"\n\n>>> Proces zakończył się. Kod: {code}\n"
        )

        self.finished.emit(code)