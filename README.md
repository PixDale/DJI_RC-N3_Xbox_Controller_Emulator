# DJI RC-N3 as Xbox 360 Controller

This script turns your **DJI RC-N3 controller** into an **Xbox 360 controller**, so you can use it with your favorite drone simulator.

![DJI RC-N3 controller with Zaphyr simulator](assets/Zephyr_simulator.jpg)

## Installation

1. Only for Mac users: first install the [Xbox 360 Controller driver](https://www.google.com/search?q=xbox+360+controller+driver+mac&oq=xbox+360+controller+driver+mac+os) for your OS version (not tested yet).
2. Download and install [DJI Assistant 2 (Consumer Drones Series)](https://www.dji.com/be/downloads/softwares/dji-assistant-2-consumer-drones-series)  
This is only needed to install the DJI drivers for the controller.  
IMPORTANT: **DO NOT** run this script while DJI Assistant 2 is running!
2. Download and install [Python 3.x.x](https://www.python.org/downloads/).
3. Install the required packages for this project: `pip3 install vgamepad pyserial`.
4. Optionally install `python-dotenv` for `.env` file support: `pip3 install python-dotenv`.

## How to use

1. Connect your DJI RC-N3 controller to your computer via the USB-C port <b style="color: darkred">ON THE BOTTOM PORT</b> (the port between the two joystick holders) of the controller.
2. Power on the controller.
3. Run `python dji.py` from the terminal to start the script.

### Command-line options

| Flag | Description |
|------|-------------|
| `-p`, `--port` | Specify the serial port manually (e.g. `-p COM5`). Auto-detected if omitted. |
| `-d`, `--debug` | Show live stick/button values in the console. |

terminal with SHOW_DEBUG=1 (animated gif)

![Working in Windows terminal, debug on](assets/debug_Animation.gif)

terminal with SHOW_DEBUG=0, perhaps faster

![Working in Windows terminal, debug off](assets/debug_off.png)

After stopping the program, session statistics are displayed (duration, packet rates, jitter distribution).

![Working in Windows terminal, ending statistic](assets/longrun.png)


4. Click `Ctrl+C` on Windows or `Cmd+C` on Mac to stop the script.

**TIP**: test if the controller works with the [Gamepad Tester](https://gamepad-tester.com/).  
Move the joysticks and the Camera Control Dial to see if the buttons are activated.

## Customization

The script maps the two joysticks, the **Camera Control Dial**, and the physical **RC buttons** (Fn, Camera, Photo, RTH) plus the **flight mode switch** to Xbox 360 controller inputs.  
All mappings are configurable via the `.env` file (or environment variables).

```bash
# Camera dial button mapping
# Available: A, B, X, Y, START, BACK, LB, RB, LS, RS, DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT
CAMERA_UP_BUTTON=Y
CAMERA_DOWN_BUTTON=B

# Camera sensitivity: 0.0-1.0 (higher = harder to trigger, default 0.98)
CAMERA_SENSITIVITY=0.98

# Physical RC button mapping
RC_FN_BUTTON=A
RC_CAMERA_BUTTON=LB
RC_PHOTO_BUTTON=X
RC_RTH_BUTTON=RB

# Flight mode switch (leave empty to disable)
# These gamepad buttons are HELD while the switch is in that position
# Normal mode = neither button pressed
RC_MODE_SPORT_BUTTON=START
RC_MODE_CINE_BUTTON=BACK

# Show live stick/button values in console (0=off, 1=on; or use -d flag)
SHOW_DEBUG=0
```

## Troubleshooting

1. You have installed the drivers for the controller with DJI Assistant 2 (Consumer Drones Series)?
2. Your controller is connected to your computer via the USB-C port **ON THE BOTTOM** of the controller?
3. Use a **good quality USB-C cable** (not all cables are capable of data transfer, some of them are from poor quality and maybe the cable is just too long).<br>
Try different cables.

If all of the above is correct, you should see the controller as **"DJI USB VCOM For Protocol (COMx)"** or **"DEVICE USB VCOM For Protocol (COMx)"** in the device manager of Windows under "Ports (COM & LPT)"<br>
![DJI USB VCOM](assets/com_ports.png)

## Simulators tested

- [Zephyr](https://zephyr-sim.com/)
- [DJI Fly Simulator](https://www.dji.com/be/downloads/products/simulator)
- [DroneSimPro](https://www.dronesimpro.com/)

## Credits

This script is based on the [Matsemann/mDjiController](https://github.com/Matsemann/mDjiController) script with extra features to customize the mapping of the Camera Control Dial.

## Contributors
- [Maaciej](https://github.com/Maaciej)
- [Konrad Iturbe](https://github.com/KonradIT)

## Change log

### **4.0.0**
- Renamed project from RC-N1 to **RC-N3**
- Added physical RC button mapping (Fn, Camera, Photo, RTH)
- Added flight mode switch mapping (Sport / Normal / Cine)
- Added CLI arguments (`-p` / `--port`, `-d` / `--debug`)
- Added `LS`, `RS`, and `DPAD_*` to available button options
- Made `python-dotenv` optional
- Removed `colorama` dependency
- Removed `BAUD_RATE` and `SHOW_GT20` settings
- Renamed camera env vars to `CAMERA_UP_BUTTON` / `CAMERA_DOWN_BUTTON`
- Renamed camera sensitivity to `CAMERA_SENSITIVITY` (new default 0.98)
- Also detects `DEVICE USB VCOM For Protocol` ports
- Session statistics printed on exit

### **1.0.3** (2023-12-23)
- Added sensitivity setting for Camera Control Dial

### **1.0.2** (2023-10-06)
- Simpler and more stable and faster
- possibility to monitor measure times greater than 20 ms
- measure of serial speed
- statistic of transmitted data and distribution of time between measure packets
  
### **1.0.11** (2023-08-31)
- More stable and with position status report.
  
### **1.0.1** (2023-07-02)
- Fallback for Windows 11: port must be configured before it can be used.

### **1.0.0** (2023-06-20)
- First release