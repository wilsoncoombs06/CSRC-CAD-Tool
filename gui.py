import sys
import cadquery as cq
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit,
    QComboBox, QPushButton, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QMessageBox, QTextEdit, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings

# Import your core pipeline modules
from configuration import MacroGeometry, MemberProfile, MastGeometry, BracingConfig, BracingStyle
from assembly import assemble_mast_section


class TrussWorker(QThread):
    """Background thread to handle step-by-step CadQuery generation and report progress."""
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, macro_geometry, corner_profile, primary_bracing, secondary_bracing, filename):
        super().__init__()
        self.macro_geometry = macro_geometry
        self.corner_profile = corner_profile
        self.primary_bracing = primary_bracing
        self.secondary_bracing = secondary_bracing
        self.filename = filename

    def run(self):
        try:
            self.progress_signal.emit(10, "Initializing geometry profiles and parameters...")
            self.msleep(150)

            self.progress_signal.emit(30, "Building structural corner posts (macro base)...")
            self.progress_signal.emit(50, "Generating 2D bracing panels and transforming to 3D faces...")
            self.progress_signal.emit(70, "Executing Boolean unions and hollow-core cutter subtractions...")

            mast_base = assemble_mast_section(
                self.macro_geometry,
                self.corner_profile,
                self.primary_bracing,
                self.secondary_bracing
            )

            self.progress_signal.emit(90, f"Translating B-Rep model and exporting to {self.filename}...")
            cq.exporters.export(mast_base, self.filename)

            self.progress_signal.emit(100, "Truss generation and STEP export completed successfully!")
            self.finished_signal.emit(self.filename)

        except Exception as e:
            self.error_signal.emit(str(e))


class TrussGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parametric Crane Truss Generator - GT CSRC")
        self.resize(600, 820)

        self.settings = QSettings("GeorgiaTech", "CraneTrussGenerator")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        title_label = QLabel("Tower Crane Truss Parametric Generator")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 5px;")
        main_layout.addWidget(title_label)

        # --- Parameters Group Box ---
        param_group = QGroupBox("Macro Geometry & Bracing Configuration")
        form_layout = QFormLayout(param_group)

        # 1. Mast Length
        self.length_input = QLineEdit()
        form_layout.addRow("Mast Length (in):", self.length_input)

        # 2. Mast Cross-Section Shape (Placed directly below length)
        self.shape_combo = QComboBox()
        self.shape_combo.addItem("")  # Blank entry if no previous entry exists
        self.shape_combo.addItems(["SQUARE", "RECTANGULAR", "TRIANGULAR"])
        self.shape_combo.currentTextChanged.connect(self.on_shape_changed)
        form_layout.addRow("Mast Cross-Section Shape:", self.shape_combo)

        # Number of Bays
        self.bays_input = QLineEdit()
        form_layout.addRow("Number of Bays:", self.bays_input)

        # Cross-Section Width
        self.width_label = QLabel("Cross-Section Width (in):")
        self.width_input = QLineEdit()
        form_layout.addRow(self.width_label, self.width_input)

        # Cross-Section Height/Depth (Rectangular only)
        self.height_label = QLabel("Cross-Section Height/Depth (in):")
        self.height_input = QLineEdit()
        form_layout.addRow(self.height_label, self.height_input)

        # Primary Bracing Style
        self.primary_label = QLabel("Primary Bracing Style:")
        self.primary_bracing_combo = QComboBox()
        self.primary_bracing_combo.addItem("")
        self.primary_bracing_combo.addItems(["INVERTED_V", "WARREN", "X_BRACE", "DIAGONAL_ONLY"])
        form_layout.addRow(self.primary_label, self.primary_bracing_combo)

        # Secondary Bracing Style
        self.secondary_label = QLabel("Secondary Bracing Style:")
        self.secondary_bracing_combo = QComboBox()
        self.secondary_bracing_combo.addItem("")
        self.secondary_bracing_combo.addItems(["INVERTED_V", "WARREN", "X_BRACE", "DIAGONAL_ONLY"])
        form_layout.addRow(self.secondary_label, self.secondary_bracing_combo)

        # Filename
        self.filename_input = QLineEdit()
        form_layout.addRow("Output STEP Filename:", self.filename_input)

        main_layout.addWidget(param_group)

        # --- Progress Bar Section ---
        progress_group = QGroupBox("Process Status")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_bar)

        main_layout.addWidget(progress_group)

        # --- Generate Button ---
        self.generate_btn = QPushButton("Generate Truss & Export STEP")
        self.generate_btn.setStyleSheet("font-weight: bold; padding: 10px; background-color: #2b5b84; color: white;")
        self.generate_btn.clicked.connect(self.start_generation)
        main_layout.addWidget(self.generate_btn)

        # --- Status Log Console ---
        log_group = QGroupBox("Execution Log")
        log_layout = QVBoxLayout(log_group)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: monospace;")
        log_layout.addWidget(self.log_console)
        main_layout.addWidget(log_group)

        self.load_settings()
        self.on_shape_changed(self.shape_combo.currentText())
        self.log("GUI initialized successfully. Ready for parameter input.")

    def log(self, message):
        self.log_console.append(message)

    def on_shape_changed(self, shape_str):
        """Show or hide width, depth, primary, and secondary fields based on shape selection."""
        is_selected = bool(shape_str and shape_str.strip())

        # Width and Primary require a shape to be selected
        self.width_label.setVisible(is_selected)
        self.width_input.setVisible(is_selected)
        self.primary_label.setVisible(is_selected)
        self.primary_bracing_combo.setVisible(is_selected)

        # Height/Depth only visible if RECTANGULAR is selected
        is_rectangular = (shape_str == "RECTANGULAR")
        self.height_label.setVisible(is_selected and is_rectangular)
        self.height_input.setVisible(is_selected and is_rectangular)

        # Secondary bracing hidden if TRIANGULAR or not selected
        is_triangular = (shape_str == "TRIANGULAR")
        self.secondary_label.setVisible(is_selected and not is_triangular)
        self.secondary_bracing_combo.setVisible(is_selected and not is_triangular)

    def load_settings(self):
        # Load previous entries or leave blank if none exist
        self.length_input.setText(self.settings.value("length", ""))
        self.shape_combo.setCurrentText(self.settings.value("shape", ""))
        self.bays_input.setText(self.settings.value("bays", ""))
        self.width_input.setText(self.settings.value("width", ""))
        self.height_input.setText(self.settings.value("height", ""))
        self.primary_bracing_combo.setCurrentText(self.settings.value("primary_bracing", ""))
        self.secondary_bracing_combo.setCurrentText(self.settings.value("secondary_bracing", ""))
        self.filename_input.setText(self.settings.value("filename", ""))

    def save_settings(self):
        self.settings.setValue("length", self.length_input.text())
        self.settings.setValue("shape", self.shape_combo.currentText())
        self.settings.setValue("bays", self.bays_input.text())
        self.settings.setValue("width", self.width_input.text())
        self.settings.setValue("height", self.height_input.text())
        self.settings.setValue("primary_bracing", self.primary_bracing_combo.currentText())
        self.settings.setValue("secondary_bracing", self.secondary_bracing_combo.currentText())
        self.settings.setValue("filename", self.filename_input.text())

    def update_progress(self, val, message):
        self.progress_bar.setValue(val)
        self.log(message)

    def start_generation(self):
        try:
            self.log("\n--- Starting New Generation Task ---")
            self.save_settings()

            shape_str = self.shape_combo.currentText()
            if not shape_str:
                raise ValueError("Please select a Mast Cross-Section Shape before generating.")

            length = float(self.length_input.text()) * 25.4
            width = float(self.width_input.text()) * 25.4

            if shape_str == "RECTANGULAR":
                height = float(self.height_input.text()) * 25.4
            else:
                height = width

            num_bays = int(self.bays_input.text())
            primary_str = self.primary_bracing_combo.currentText()
            secondary_str = self.secondary_bracing_combo.currentText() if shape_str != "TRIANGULAR" else "DIAGONAL_ONLY"
            filename = self.filename_input.text()

            if not primary_str:
                raise ValueError("Please select a Primary Bracing Style.")

            mast_geo_enum = getattr(MastGeometry, shape_str)
            primary_style_enum = getattr(BracingStyle, primary_str)
            secondary_style_enum = getattr(BracingStyle, secondary_str) if shape_str != "TRIANGULAR" else BracingStyle.DIAGONAL_ONLY

            self.log(f"Parameters: Shape={shape_str}, Length={length / 25.4:.1f}in, Width={width / 25.4:.1f}in, Height={height / 25.4:.1f}in")
            self.log(f"Bracing: Primary={primary_str}, Secondary={secondary_str if shape_str != 'TRIANGULAR' else 'N/A'}, Bays={num_bays}")

            corner_profile = MemberProfile(
                shape='hollow_rectangle', width=10 * 25.4, height=10 * 25.4, wall_thickness=0.625 * 25.4
            )

            macro_geometry = MacroGeometry(
                length=length,
                width=width,
                height=height,
                main_chord_profile=corner_profile,
                cross_section_shape=mast_geo_enum
            )

            web_profile = MemberProfile(
                shape='hollow_rectangle', width=5 * 25.4, height=5 * 25.4, wall_thickness=0.500 * 25.4
            )

            primary_bracing = BracingConfig(
                style=primary_style_enum,
                num_bays=num_bays,
                diagonal_profile=web_profile,
                has_horizontal_struts=True,
                horizontal_profile=web_profile,
                has_cap_struts=True,
                cap_strut_profile=web_profile
            )

            secondary_bracing = BracingConfig(
                style=secondary_style_enum,
                num_bays=num_bays,
                diagonal_profile=web_profile,
                has_cap_struts=True,
                cap_strut_profile=web_profile
            )

            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("Generating Model (Please Wait)...")
            self.progress_bar.setValue(0)

            # Launch worker thread
            self.worker = TrussWorker(
                macro_geometry, corner_profile, primary_bracing, secondary_bracing, filename
            )
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_generation_finished)
            self.worker.error_signal.connect(self.on_generation_error)
            self.worker.start()

        except Exception as e:
            self.log(f"ERROR: {str(e)}")
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate Truss & Export STEP")
            QMessageBox.critical(self, "Error", f"Failed to start generation:\n{str(e)}")

    def on_generation_finished(self, filename):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Truss & Export STEP")
        QMessageBox.information(self, "Success", f"Truss successfully generated and exported to {filename}!")

    def on_generation_error(self, error_msg):
        self.log(f"ERROR: {error_msg}")
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Truss & Export STEP")
        QMessageBox.critical(self, "Generation Error", f"Failed to generate truss:\n{error_msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TrussGUI()
    window.show()
    sys.exit(app.exec())