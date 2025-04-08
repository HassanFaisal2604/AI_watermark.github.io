# Install Python and pip if not available
apt-get update && apt-get install -y python3 python3-pip
python3 -m pip install --upgrade pip
pip3 install -r requirements.txt