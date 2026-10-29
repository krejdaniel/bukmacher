from pathlib import Path
import pandas as pd

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QMessageBox
)

from services.runner import ProcessRunner, BACKEND


class HomeWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.runner = ProcessRunner()

        self.setWindowTitle("Football Predictor")
        self.resize(700, 600)

        layout = QVBoxLayout()

        # ==========================
        # Tytuł
        # ==========================

        title = QLabel("Football Predictor")
        title.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
        """)

        layout.addWidget(title)

        # ==========================
        # Przyciski
        # ==========================

        self.btn_backtest = QPushButton("Testy modelu")
        self.btn_predict = QPushButton("Predict")
        self.btn_bankroll = QPushButton("Aktualny portfel")
        self.btn_history = QPushButton("Historia testów")
        self.btn_exit = QPushButton("Wyjdź")

        self.btn_backtest.clicked.connect(self.run_backtest)
        self.btn_predict.clicked.connect(self.run_predict)

        self.btn_bankroll.clicked.connect(self.show_portfolio)
        self.btn_history.clicked.connect(self.show_history)

        self.btn_exit.clicked.connect(self.close)

        layout.addWidget(self.btn_backtest)
        layout.addWidget(self.btn_predict)
        layout.addWidget(self.btn_bankroll)
        layout.addWidget(self.btn_history)

        layout.addStretch()

        # ==========================
        # Log
        # ==========================

        log_label = QLabel("Log")

        log_label.setStyleSheet("""
            font-size:16px;
            font-weight:bold;
        """)

        layout.addWidget(log_label)

        self.console = QTextEdit()
        self.console.setReadOnly(True)

        layout.addWidget(self.console)

        # ==========================
        # Wyjście
        # ==========================

        layout.addWidget(self.btn_exit)

        self.setLayout(layout)

        # ==========================
        # Sygnały
        # ==========================

        self.runner.output.connect(self.append_output)
        self.runner.finished.connect(self.process_finished)

    def clear_log(self):
        self.console.clear()

    def run_backtest(self):
        self.console.clear()
        self.runner.run_backtest()


    def run_predict(self):
        self.console.clear()
        self.runner.run_predict()

    def append_output(self, text):
        cursor = self.console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.console.setTextCursor(cursor)

        self.console.insertPlainText(text)
        self.console.ensureCursorVisible()

    def show_portfolio(self):

        portfolio_file = BACKEND / "portfolio.csv"

        if not portfolio_file.exists():
            QMessageBox.information(
                self,
                "Portfel",
                "Plik portfolio.csv jeszcze nie istnieje."
            )
            return

        try:
            df = pd.read_csv(
                portfolio_file,
                sep=";",
                decimal=",",
                encoding="utf-8-sig"
            )

            self.console.clear()

            self.console.append(
                "=============================="
            )

            self.console.append(
                "AKTUALNY PORTFEL"
            )

            self.console.append(
                "==============================\n"
            )

            self.console.append(
                df.to_string(index=False)
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Błąd",
                f"Nie udało się odczytać portfela:\n{e}"
            )


    def show_history(self):

        history_dir = BACKEND / "history"

        if not history_dir.exists():
            QMessageBox.information(
                self,
                "Historia",
                "Folder history jeszcze nie istnieje."
            )
            return

        files = sorted(
            history_dir.glob("*.csv"),
            reverse=True
        )

        if not files:
            QMessageBox.information(
                self,
                "Historia",
                "Brak zapisanych testów."
            )
            return

        self.console.clear()

        self.console.append(
            "=============================="
        )

        self.console.append(
            "HISTORIA TESTÓW"
        )

        self.console.append(
            "==============================\n"
        )

        for file in files:

            self.console.append(
                file.name
            )

    def process_finished(self, code):
        self.console.append(f"\n Proces zakończony (kod: {code})\n")