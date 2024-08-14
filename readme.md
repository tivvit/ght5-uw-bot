# Unnatural Worlds - Python example bot

## Installation

To install the bot, you will need to have Python 3 installed. Once you have it, you can create a virtual environment:

```bash
python3 -m venv venv
```

Once the virtual environment is created, you can activate it and install the bot's dependencies:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Set the STEAM_PATH env variable (if you are not using the standard path) and run the bot.

```bash
export UNNATURAL_ROOT="~/.local/share/Steam/common/Unnatural Worlds/bin"
python main.py
```

## Steam in Flatpak

If you have Steam installed via Flatpak we have bad news for you ...

Flatpak is a containerized environment even if you enable access the development directory you can enter the container
via the command below, but you will be missing the Python runtime.

```bash
flatpak enter com.valvesoftware.Steam /bin/bash
export HOME=/home/${YOUR_USER} DISPLAY=:0
```

There may be a way using Flatpak extensions but we did not fully explore that. 