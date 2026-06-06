import wmi
import psutil
import datetime
import re
import subprocess

# ─── USB Vendor ID database (most common vendors) ──────────────────────────
# Maps USB VID (hex) to manufacturer name
USB_VENDORS = {
    "0451": "Texas Instruments",
    "045E": "Microsoft",
    "046D": "Logitech",
    "047F": "Plantronics",
    "048D": "ITE Tech",
    "04D8": "Microchip",
    "04F2": "Chicony Electronics",
    "054C": "Sony",
    "0572": "Conexant",
    "05AC": "Apple",
    "05E3": "Genesys Logic",
    "0738": "Mad Catz",
    "0763": "M-Audio",
    "0810": "Personal Communication Systems",
    "0951": "Kingston Technology",
    "09DA": "A4Tech",
    "0B05": "ASUS",
    "0C45": "Microdia / Sonix Technology",
    "0C76": "JMTek",
    "0D8C": "C-Media Electronics",
    "1038": "SteelSeries",
    "1050": "Yubico",
    "10C4": "Silicon Labs",
    "1130": "Tenx Technology",
    "1235": "Focusrite",
    "12D1": "Huawei",
    "1395": "Sennheiser",
    "1462": "MSI",
    "1532": "Razer",
    "17EF": "Lenovo",
    "1B1C": "Corsair",
    "1B3F": "Generalplus Technology",
    "1D50": "OpenMoko",
    "1E71": "NZXT",
    "2109": "VIA Labs (USB Hub)",
    "2516": "Cooler Master",
    "258A": "SINO WEALTH",
    "26CE": "LED Controller / Razer",
    "2B24": "Finalmouse",
    "2F68": "Wooting",
    "3151": "Yealink",
    "320F": "Glorious",
    "33FA": "Barrot Technology",
    "3434": "Keychron",
    "3554": "XTRFY",
    "8087": "Intel Corp.",
    "B58E": "Blue Microphones",
}

# ─── USB Product ID database (VID:PID -> product name + category) ───────────
# category: keyboard, mouse, headset, microphone, webcam, receiver, controller, other
USB_PRODUCTS = {
    # Corsair keyboards
    "1B1C:1B2D": ("Corsair K65 RGB", "keyboard"),
    "1B1C:1B33": ("Corsair K70 LUX RGB", "keyboard"),
    "1B1C:1B49": ("Corsair K70 RGB MK.2", "keyboard"),
    "1B1C:1B55": ("Corsair K95 RGB Platinum", "keyboard"),
    "1B1C:1B6B": ("Corsair K100 RGB", "keyboard"),
    "1B1C:1BDC": ("Corsair K70 CORE RGB", "keyboard"),
    "1B1C:1B4F": ("Corsair K68 RGB", "keyboard"),
    # Corsair mice
    "1B1C:1B2E": ("Corsair M65 RGB", "mouse"),
    "1B1C:1B5A": ("Corsair IRONCLAW RGB", "mouse"),
    "1B1C:1B75": ("Corsair KATAR PRO", "mouse"),
    # Corsair headsets
    "1B1C:0A38": ("Corsair VOID PRO", "headset"),
    "1B1C:0A55": ("Corsair HS80 RGB", "headset"),
    # Logitech
    "046D:C52B": ("Logitech Unifying Receiver", "receiver"),
    "046D:C52F": ("Logitech Unifying Receiver", "receiver"),
    "046D:C539": ("Logitech Lightspeed Receiver", "receiver"),
    "046D:C53A": ("Logitech Lightspeed Receiver", "receiver"),
    "046D:C53F": ("Logitech Lightspeed Receiver", "receiver"),
    "046D:C547": ("Logitech Bolt Receiver", "receiver"),
    "046D:C08B": ("Logitech G502 HERO", "mouse"),
    "046D:C332": ("Logitech G502", "mouse"),
    "046D:C07E": ("Logitech G402", "mouse"),
    "046D:C083": ("Logitech G403", "mouse"),
    "046D:C084": ("Logitech G203", "mouse"),
    "046D:C092": ("Logitech G102/G203", "mouse"),
    "046D:C33C": ("Logitech G513", "keyboard"),
    "046D:C339": ("Logitech G PRO Keyboard", "keyboard"),
    # Razer
    "1532:0084": ("Razer DeathAdder V2", "mouse"),
    "1532:007A": ("Razer Viper", "mouse"),
    "1532:0078": ("Razer Basilisk V2", "mouse"),
    "1532:0241": ("Razer Huntsman V2", "keyboard"),
    "1532:0256": ("Razer Huntsman Mini", "keyboard"),
    # JMTek / Razer Seiren
    "0C76:1273": ("Razer Seiren Mini", "microphone"),
    # SteelSeries
    "1038:1729": ("SteelSeries Arctis 7", "headset"),
    "1038:12AD": ("SteelSeries Rival 600", "mouse"),
    # Generic webcams
    "0C45:636A": ("T1A Webcam", "webcam"),
    # Finalmouse
    "2B24:0001": ("Finalmouse Starlight-12", "mouse"),
    # Glorious
    "320F:5044": ("Glorious Model O", "mouse"),
    "320F:5092": ("Glorious Model D", "mouse"),
}


def get_size(bytes_val, suffix="B"):
    """Scale bytes to its proper format."""
    if bytes_val is None or bytes_val == 0:
        return "0 B"
    bytes_val = abs(int(bytes_val))
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes_val < factor:
            return f"{bytes_val:.2f} {unit}{suffix}"
        bytes_val /= factor
    return f"{bytes_val:.2f} P{suffix}"


def _parse_vid_pid(device_id: str):
    """Extract VID and PID from a PnP device ID string."""
    m = re.search(r'VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})', device_id)
    if m:
        return m.group(1).upper(), m.group(2).upper()
    return None, None


def _resolve_vendor(vid: str) -> str:
    """Look up a USB Vendor ID in the local database."""
    return USB_VENDORS.get(vid, f"Unknown (VID:{vid})")


class HardwareDetector:
    def __init__(self):
        self.c = wmi.WMI()

    # ───────── System Summary ─────────
    def get_system_info(self):
        info = {}
        for cs in self.c.Win32_ComputerSystem():
            info["Manufacturer"] = cs.Manufacturer or "Unknown"
            info["Model"] = cs.Model or "Unknown"
            info["System Type"] = cs.SystemType or "Unknown"
        for os_info in self.c.Win32_OperatingSystem():
            info["OS"] = os_info.Caption or "Unknown"
            info["OS Version"] = os_info.Version or "Unknown"
            info["OS Architecture"] = os_info.OSArchitecture or "Unknown"
        return info

    # ───────── BIOS ─────────
    def get_bios_info(self):
        bios_list = []
        for bios in self.c.Win32_BIOS():
            date_raw = bios.ReleaseDate or ""
            date_formatted = date_raw
            if date_raw and len(date_raw) >= 8:
                try:
                    date_formatted = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                except Exception:
                    pass
            bios_list.append({
                "Manufacturer": bios.Manufacturer or "Unknown",
                "Version": bios.SMBIOSBIOSVersion or bios.Version or "Unknown",
                "Release Date": date_formatted
            })
        return bios_list

    # ───────── CPU ─────────
    def get_cpu_info(self):
        cpus = []
        for processor in self.c.Win32_Processor():
            cpu_info = {
                "Name": processor.Name.strip() if processor.Name else "Unknown",
                "Cores": processor.NumberOfCores,
                "Logical Processors": processor.NumberOfLogicalProcessors,
                "Max Clock Speed": f"{processor.MaxClockSpeed} MHz" if processor.MaxClockSpeed else "Unknown",
                "Architecture": processor.Architecture,
                "L2 Cache": f"{processor.L2CacheSize} KB" if processor.L2CacheSize else "N/A",
                "L3 Cache": f"{processor.L3CacheSize} KB" if processor.L3CacheSize else "N/A",
            }
            cpus.append(cpu_info)
        return cpus

    # ───────── Motherboard ─────────
    def get_motherboard_info(self):
        boards = []
        for board in self.c.Win32_BaseBoard():
            board_info = {
                "Manufacturer": board.Manufacturer or "Unknown",
                "Product": board.Product or "Unknown",
                "Version": board.Version or "Unknown",
                "Serial Number": board.SerialNumber or "N/A"
            }
            boards.append(board_info)
        return boards

    # ───────── GPU (with registry VRAM fallback) ─────────
    def get_gpu_info(self):
        gpus = []

        # Try to get accurate VRAM from registry via a temp PowerShell script
        # Uses qwMemorySize (64-bit) which doesn't have the 4GB WMI overflow issue
        vram_registry = {}  # Maps lowercase driver desc -> vram bytes
        try:
            import tempfile, os
            ps_script = (
                "Get-ChildItem 'HKLM:\\SYSTEM\\ControlSet001\\Control\\Class\\"
                "{4d36e968-e325-11ce-bfc1-08002be10318}' -EA SilentlyContinue | "
                "ForEach-Object {\n"
                "    $props = Get-ItemProperty $_.PSPath -EA SilentlyContinue\n"
                "    $desc = $props.DriverDesc\n"
                "    $qw = $props.'HardwareInformation.qwMemorySize'\n"
                '    Write-Output "$desc|$qw"\n'
                "}\n"
            )
            # Write to a temp file and execute it
            tmp_path = os.path.join(tempfile.gettempdir(), "_pcdetection_vram.ps1")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(ps_script)

            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp_path],
                capture_output=True, text=True, timeout=10
            )

            try:
                os.remove(tmp_path)
            except Exception:
                pass

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if '|' in line:
                        parts = line.split('|', 1)
                        name = parts[0].strip()
                        val = parts[1].strip()
                        if name and val:
                            try:
                                vram_bytes = int(val)
                                vram_registry[name.lower()] = vram_bytes
                            except (ValueError, IndexError):
                                pass
        except Exception:
            pass

        for gpu in self.c.Win32_VideoController():
            gpu_name = gpu.Name or "Unknown"

            # Priority: registry qwMemorySize > WMI AdapterRAM (with 4GB overflow fix)
            vram = "Unknown"
            if gpu_name.lower() in vram_registry:
                vram = get_size(vram_registry[gpu_name.lower()])
            elif gpu.AdapterRAM:
                ram = int(gpu.AdapterRAM)
                # WMI returns a signed 32-bit int; for GPUs >2GB it wraps negative
                # For GPUs >4GB, the value wraps to a small positive. Detect this.
                if ram < 0:
                    # Negative means > 2GB, convert unsigned
                    ram = ram + (1 << 32)
                elif 0 < ram < 512 * 1024 * 1024:
                    # Suspiciously small for a discrete GPU, likely 4GB+ overflow
                    # Only apply heuristic for discrete GPUs (not virtual adapters)
                    if any(kw in gpu_name.lower() for kw in ['nvidia', 'geforce', 'rtx', 'gtx', 'radeon', 'rx ']):
                        ram = ram + (1 << 32)
                vram = get_size(abs(ram))

            gpu_info = {
                "Name": gpu_name,
                "VRAM": vram,
                "Driver Version": gpu.DriverVersion or "Unknown",
                "Driver Date": gpu.DriverDate[:8] if gpu.DriverDate and len(gpu.DriverDate) >= 8 else "Unknown",
                "Resolution": f"{gpu.CurrentHorizontalResolution}x{gpu.CurrentVerticalResolution}" if gpu.CurrentHorizontalResolution else "N/A",
                "Refresh Rate": f"{gpu.CurrentRefreshRate} Hz" if gpu.CurrentRefreshRate else "N/A",
                "Status": gpu.Status or "Unknown",
            }
            gpus.append(gpu_info)
        return gpus

    # ───────── RAM ─────────
    def get_ram_info(self):
        ram_modules = []
        form_factor_map = {
            0: "Unknown", 1: "Other", 2: "SIP", 3: "DIP", 5: "SOJ",
            8: "DIMM", 9: "TSOP", 12: "RIMM", 13: "SODIMM", 15: "FB-DIMM"
        }
        memory_type_map = {
            0: "Unknown", 20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
            24: "DDR3", 26: "DDR4", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"
        }

        for memory in self.c.Win32_PhysicalMemory():
            capacity = int(memory.Capacity) if memory.Capacity else 0
            form = form_factor_map.get(memory.FormFactor, f"Code {memory.FormFactor}") if memory.FormFactor else "Unknown"
            mem_type = memory_type_map.get(memory.SMBIOSMemoryType, f"Code {memory.SMBIOSMemoryType}") if memory.SMBIOSMemoryType else "Unknown"

            ram_info = {
                "Manufacturer": (memory.Manufacturer or "Unknown").strip(),
                "Capacity": get_size(capacity),
                "Speed": f"{memory.Speed} MHz" if memory.Speed else "Unknown",
                "Configured Speed": f"{memory.ConfiguredClockSpeed} MHz" if hasattr(memory, 'ConfiguredClockSpeed') and memory.ConfiguredClockSpeed else "N/A",
                "Part Number": (memory.PartNumber or "Unknown").strip(),
                "Form Factor": form,
                "Type": mem_type,
                "Slot": memory.DeviceLocator or "Unknown"
            }
            ram_modules.append(ram_info)

        svmem = psutil.virtual_memory()

        return {
            "Total Capacity": get_size(svmem.total),
            "Modules": ram_modules
        }

    # ───────── Storage (using MSFT_PhysicalDisk for accurate type detection) ─────────
    def get_storage_info(self):
        drives = []
        media_map = {0: "Unspecified", 3: "HDD", 4: "SSD", 5: "SCM"}
        bus_map = {
            0: "Unknown", 1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "IEEE 1394",
            5: "SSA", 6: "Fibre Channel", 7: "USB", 8: "RAID", 9: "iSCSI",
            10: "SAS", 11: "SATA", 12: "SD", 13: "MMC", 14: "MAX",
            15: "File Backed Virtual", 16: "Storage Spaces", 17: "NVMe"
        }
        health_map = {0: "Healthy", 1: "Warning", 2: "Unhealthy", 5: "Unknown"}

        try:
            storage_wmi = wmi.WMI(namespace='root\\microsoft\\windows\\storage')
            for d in storage_wmi.MSFT_PhysicalDisk():
                size = int(d.Size) if d.Size else 0
                media_type = media_map.get(d.MediaType, f"Code {d.MediaType}")
                bus_type = bus_map.get(d.BusType, f"Code {d.BusType}")
                health = health_map.get(d.HealthStatus, f"Code {d.HealthStatus}") if hasattr(d, 'HealthStatus') else "Unknown"

                drive_info = {
                    "Model": d.FriendlyName or d.Model or "Unknown",
                    "Size": get_size(size),
                    "Type": media_type,
                    "Bus": bus_type,
                    "Health": health,
                    "Serial": (d.SerialNumber or "N/A").strip(),
                    "Firmware": (d.FirmwareVersion or "N/A").strip()
                }
                drives.append(drive_info)
        except Exception:
            # Fallback to Win32_DiskDrive
            for drive in self.c.Win32_DiskDrive():
                size = int(drive.Size) if drive.Size else 0
                drive_info = {
                    "Model": drive.Model or "Unknown",
                    "Size": get_size(size),
                    "Type": "Unknown",
                    "Bus": drive.InterfaceType or "Unknown",
                    "Health": "N/A",
                    "Serial": (drive.SerialNumber or "N/A").strip(),
                    "Firmware": (drive.FirmwareRevision or "N/A").strip()
                }
                drives.append(drive_info)
        return drives

    # ───────── Monitors (EDID via WmiMonitorID) ─────────
    def get_monitor_info(self):
        monitors = []
        try:
            w = wmi.WMI(namespace='root\\wmi')
            for mon in w.WmiMonitorID():
                mfr = ''.join(chr(c) for c in mon.ManufacturerName if c != 0) if mon.ManufacturerName else "Unknown"
                model = ''.join(chr(c) for c in mon.UserFriendlyName if c != 0) if mon.UserFriendlyName else "N/A"
                serial = ''.join(chr(c) for c in mon.SerialNumberID if c != 0) if mon.SerialNumberID else "N/A"

                monitors.append({
                    "Manufacturer Code": mfr,
                    "Model": model if model else "N/A",
                    "Serial": serial,
                    "Year": mon.YearOfManufacture if hasattr(mon, 'YearOfManufacture') else "N/A"
                })
        except Exception:
            # Fallback
            for monitor in self.c.Win32_DesktopMonitor():
                monitors.append({
                    "Manufacturer Code": "Unknown",
                    "Model": monitor.Name or monitor.MonitorType or "Unknown",
                    "Serial": "N/A",
                    "Year": "N/A"
                })
        return monitors

    # ───────── USB Peripherals (precise VID/PID detection) ─────────
    def get_usb_peripherals(self):
        """Detect real USB peripherals by VID/PID, using product DB + HID class scanning."""
        peripherals = {
            "Keyboards": [],
            "Mice": [],
            "Audio": [],
            "Webcams": [],
            "Controllers": [],
            "Other USB": [],
        }

        skip_name_patterns = [
            "concentrador", "hub", "root_hub",
            "compuesto", "composite",
            "enumerador", "umbus",
        ]

        seen_vidpid = set()  # deduplicate by VID+PID

        # --- Step 1: Determine what HID classes each VID:PID exposes ---
        # By scanning ALL PnP entities (including HID children), we can find
        # the actual device class (Keyboard, Mouse, etc.) for each VID:PID.
        vidpid_classes = {}  # "VID:PID" -> set of PNPClass values
        vidpid_services = {}  # "VID:PID" -> set of Service values
        vidpid_names = {}  # "VID:PID" -> best display name found

        for dev in self.c.Win32_PnPEntity():
            did = dev.DeviceID or ""
            vid, pid = _parse_vid_pid(did)
            if not vid:
                continue

            key = f"{vid}:{pid}"
            pnp_class = (dev.PNPClass or "").lower() if hasattr(dev, 'PNPClass') else ""
            service = (dev.Service or "").lower() if hasattr(dev, 'Service') else ""
            name = dev.Name or ""

            if key not in vidpid_classes:
                vidpid_classes[key] = set()
                vidpid_services[key] = set()
                vidpid_names[key] = ""

            if pnp_class:
                vidpid_classes[key].add(pnp_class)
            if service:
                vidpid_services[key].add(service)

            # Keep the most descriptive name (not generic "Dispositivo de entrada USB")
            name_lower = name.lower()
            is_generic = any(g in name_lower for g in ["dispositivo de entrada", "input device", "compuesto", "composite"])
            if name and not is_generic:
                vidpid_names[key] = name

        # --- Step 2: Build peripheral entries from USB-level devices ---
        for dev in self.c.Win32_PnPEntity():
            did = dev.DeviceID or ""
            # Only process top-level USB devices (not HID children)
            if not did.startswith("USB\\"):
                continue

            name = dev.Name or ""
            name_lower = name.lower()

            # Skip infrastructure
            if any(p in name_lower for p in skip_name_patterns):
                continue
            if any(p in did.lower() for p in ["root_hub", "ts_usb_hub"]):
                continue

            vid, pid = _parse_vid_pid(did)
            if not vid:
                continue

            key = f"{vid}:{pid}"
            if key in seen_vidpid:
                continue
            seen_vidpid.add(key)

            vendor = _resolve_vendor(vid)
            classes = vidpid_classes.get(key, set())
            services = vidpid_services.get(key, set())
            best_name = vidpid_names.get(key, "")

            # --- Determine display name ---
            # Priority: USB_PRODUCTS DB > descriptive WMI name > vendor fallback
            product_info = USB_PRODUCTS.get(key)
            if product_info:
                display_name = f"{product_info[0]} ({vendor})"
                category = product_info[1]
            else:
                if best_name:
                    display_name = f"{best_name} ({vendor})"
                else:
                    display_name = f"{vendor} Device (VID:{vid} PID:{pid})"
                category = None  # will be inferred below

            entry = {
                "Name": display_name,
                "VID": vid,
                "PID": pid,
                "Vendor": vendor,
            }

            # --- Categorize ---
            if category:
                # Known product from DB
                cat_map = {
                    "keyboard": "Keyboards",
                    "mouse": "Mice",
                    "headset": "Audio",
                    "microphone": "Audio",
                    "webcam": "Webcams",
                    "receiver": "Controllers",
                    "controller": "Controllers",
                    "other": "Other USB",
                }
                peripherals[cat_map.get(category, "Other USB")].append(entry)
            else:
                # Infer from HID class/service data
                if "keyboard" in classes or "kbdhid" in services or "kbdclass" in services:
                    peripherals["Keyboards"].append(entry)
                elif "mouse" in classes or "mouhid" in services or "mouclass" in services:
                    peripherals["Mice"].append(entry)
                elif "audio" in name_lower or "microphone" in name_lower or "seiren" in name_lower or "media" in classes:
                    peripherals["Audio"].append(entry)
                elif "camera" in classes or "webcam" in name_lower or "camera" in name_lower:
                    peripherals["Webcams"].append(entry)
                elif "bluetooth" in name_lower:
                    peripherals["Other USB"].append(entry)
                elif "hidclass" in services or "hid" in classes:
                    peripherals["Controllers"].append(entry)
                else:
                    peripherals["Other USB"].append(entry)

        # Also get audio devices from Win32_SoundDevice for system audio
        system_audio = []
        for audio in self.c.Win32_SoundDevice():
            if audio.Name:
                system_audio.append(audio.Name)
        peripherals["System Audio"] = system_audio

        return peripherals

    # ───────── Network Adapters ─────────
    def get_network_info(self):
        adapters = []
        for net in self.c.Win32_NetworkAdapter():
            if net.PhysicalAdapter:
                adapters.append({
                    "Name": net.Name or "Unknown",
                    "MAC": net.MACAddress or "N/A",
                    "Type": net.AdapterType or "Unknown",
                    "Manufacturer": net.Manufacturer or "Unknown",
                    "Speed": get_size(int(net.Speed)) + "/s" if net.Speed else "N/A"
                })
        return adapters

    # ═══════════════════════════════════════════════════════
    # Markdown Report Generator
    # ═══════════════════════════════════════════════════════
    def generate_markdown(self):
        md = "# 🖥️ Reporte de Hardware\n\n"
        md += f"**Fecha de generación:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "---\n\n"

        # System Summary
        sys_info = self.get_system_info()
        md += "## 📋 Sistema\n"
        for key, val in sys_info.items():
            md += f"- **{key}:** {val}\n"
        md += "\n"

        # BIOS
        md += "## 🔧 BIOS\n"
        for bios in self.get_bios_info():
            md += f"- **Fabricante:** {bios['Manufacturer']}\n"
            md += f"- **Versión:** {bios['Version']}\n"
            md += f"- **Fecha:** {bios['Release Date']}\n"
        md += "\n"

        # CPU
        md += "## 💻 Procesador (CPU)\n"
        for cpu in self.get_cpu_info():
            md += f"- **Modelo:** {cpu['Name']}\n"
            md += f"- **Núcleos:** {cpu['Cores']} ({cpu['Logical Processors']} Hilos)\n"
            md += f"- **Velocidad Máxima:** {cpu['Max Clock Speed']}\n"
            md += f"- **Caché L2:** {cpu['L2 Cache']} | **Caché L3:** {cpu['L3 Cache']}\n"
            md += "\n"

        # Motherboard
        md += "## 🖨️ Placa Base (Motherboard)\n"
        for board in self.get_motherboard_info():
            md += f"- **Fabricante:** {board['Manufacturer']}\n"
            md += f"- **Modelo:** {board['Product']}\n"
            md += f"- **Versión:** {board['Version']}\n"
            md += f"- **Serial:** {board['Serial Number']}\n"
            md += "\n"

        # GPU
        md += "## 🎮 Tarjeta Gráfica (GPU)\n"
        for gpu in self.get_gpu_info():
            md += f"- **Modelo:** {gpu['Name']}\n"
            md += f"- **VRAM:** {gpu['VRAM']}\n"
            md += f"- **Driver:** v{gpu['Driver Version']}\n"
            md += f"- **Resolución Actual:** {gpu['Resolution']} @ {gpu['Refresh Rate']}\n"
            md += f"- **Estado:** {gpu['Status']}\n"
            md += "\n"

        # RAM
        ram_data = self.get_ram_info()
        md += "## 🧠 Memoria RAM\n"
        md += f"- **Capacidad Total:** {ram_data['Total Capacity']}\n\n"
        if ram_data['Modules']:
            md += "| Slot | Fabricante | Capacidad | Velocidad | Tipo | Part Number |\n"
            md += "|------|-----------|-----------|-----------|------|-------------|\n"
            for mod in ram_data['Modules']:
                md += f"| {mod['Slot']} | {mod['Manufacturer']} | {mod['Capacity']} | {mod['Speed']} | {mod['Type']} | {mod['Part Number']} |\n"
        md += "\n"

        # Storage
        md += "## 💾 Almacenamiento\n"
        storage = self.get_storage_info()
        if storage:
            md += "| Modelo | Capacidad | Tipo | Bus | Estado | Firmware |\n"
            md += "|--------|-----------|------|-----|--------|----------|\n"
            for disk in storage:
                md += f"| {disk['Model']} | {disk['Size']} | {disk['Type']} | {disk['Bus']} | {disk['Health']} | {disk['Firmware']} |\n"
        md += "\n"

        # Network
        md += "## 🌐 Red\n"
        network = self.get_network_info()
        for adapter in network:
            md += f"- **{adapter['Name']}**\n"
            md += f"  - Fabricante: {adapter['Manufacturer']}\n"
            md += f"  - MAC: {adapter['MAC']}\n"
            md += f"  - Tipo: {adapter['Type']}\n"
            md += f"  - Velocidad: {adapter['Speed']}\n"
        if not network:
            md += "- No se detectaron adaptadores físicos.\n"
        md += "\n"

        # Monitors
        md += "## 🖥️ Monitores\n"
        monitors = self.get_monitor_info()
        for mon in monitors:
            md += f"- **{mon['Manufacturer Code']}** — {mon['Model']}\n"
            md += f"  - Serial: {mon['Serial']}\n"
            md += f"  - Año de fabricación: {mon['Year']}\n"
        if not monitors:
            md += "- No detectado\n"
        md += "\n"

        # USB Peripherals
        periph = self.get_usb_peripherals()
        md += "## ⌨️ Periféricos USB\n\n"

        sections = [
            ("Teclados", "Keyboards"),
            ("Ratones / Apuntadores", "Mice"),
            ("Audio USB", "Audio"),
            ("Webcams", "Webcams"),
            ("Controladores / Gamepads", "Controllers"),
            ("Otros Dispositivos USB", "Other USB"),
        ]

        for title, key in sections:
            items = periph.get(key, [])
            md += f"### {title}\n"
            if items:
                for item in items:
                    md += f"- **{item['Name']}**\n"
                    md += f"  - VID: `{item['VID']}` | PID: `{item['PID']}`\n"
            else:
                md += "- No detectado\n"
            md += "\n"

        # System Audio Devices
        sys_audio = periph.get("System Audio", [])
        md += "### Dispositivos de Audio del Sistema\n"
        for item in set(sys_audio):
            md += f"- {item}\n"
        if not sys_audio:
            md += "- No detectado\n"
        md += "\n"

        md += "---\n"
        md += f"*Generado por PCDetection*\n"

        return md


if __name__ == '__main__':
    detector = HardwareDetector()
    print(detector.generate_markdown())
