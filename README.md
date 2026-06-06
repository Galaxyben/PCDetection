# ⚡ PCDetection

PCDetection is a lightweight, modern Windows hardware scanner written in Python. It features a sleek dark-themed GUI built with **PyQt6** and utilizes **WMI** and **psutil** to query detailed system specifications, generating a well-structured hardware report in Markdown format.

---

## Features

- **Comprehensive Hardware Audit:** Scans CPU, GPU, RAM, Motherboard, BIOS, OS, Storage, and Network info.
- **Modern Dark UI:** Responsive GUI styled with a clean, modern dark mode inspired by GitHub's aesthetic.
- **Live Preview:** View the generated Markdown report instantly within the app.
- **Copy to Clipboard:** Copy the entire report in one click for sharing or logging.
- **Save to File:** Export the report as a `.md` file with an automatic timestamped filename.
- **Standalone Executable:** Compiled as a single, portable `.exe` with PyInstaller.

---

## Screenshot
<img width="682" height="612" alt="image" src="https://github.com/user-attachments/assets/bca7f1db-b1c9-4b2a-b6b6-cd2c30cf91d3" />


---

## Installation & Setup

### Prerequisites
- **Windows OS** (WMI query support is required)
- **Python 3.10+**

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/Galaxyben/PCDetection.git
   cd PCDetection
   ```

2. Create a virtual environment and activate it:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

---

## Compiling to Standalone Executable (.exe)

You can package the application into a standalone Windows executable using PyInstaller.

1. Ensure the virtual environment is active.
2. Run the provided build script:
   ```powershell
   .\build.ps1
   ```
3. Find your portable `PCDetection.exe` inside the `dist/` directory.

---

## Technologies Used

- **Python** (Core Language)
- **PyQt6** (GUI Framework)
- **psutil** (System & Process Utilities)
- **WMI** (Windows Management Instrumentation Wrapper)
- **PyInstaller** (Application Packaging)

---

## License

This project is licensed under the MIT License.
