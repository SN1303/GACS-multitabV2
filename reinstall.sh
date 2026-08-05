#!/bin/bash

# ============================================================================
# SCRIPT REINSTALL BERSIH (CLEAN UNINSTALL & REINSTALL) GENIEACS MULTITAB V2
# ============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Cek apakah dijalankan sebagai root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Harap jalankan script ini sebagai root (sudo bash reinstall.sh)${NC}"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
local_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || echo "Unknown")
UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "Unknown")
ARCH=$(uname -m)

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}==================  GENIEACS MULTITAB V2 - REINSTALL  ======================${NC}"
echo -e "${GREEN}==================  UNINSTALL BERSIH & REINSTALL FRESH  ====================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}OS System : Ubuntu ${UBUNTU_VERSION} (${UBUNTU_CODENAME}) - ${ARCH}${NC}"
echo -e "${GREEN}IP Server : ${local_ip}${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${YELLOW}Script ini akan menghapus instalasi lama secara bersih (Clean Uninstall)${NC}"
echo -e "${YELLOW}dan menginstal ulang Node.js, MongoDB, GenieACS Multitab V2 & Database.${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${RED}Apakah Anda yakin ingin melakukan Reinstall bersih? (y/n)${NC}"
read confirmation

if [ "$confirmation" != "y" ]; then
    echo -e "${YELLOW}Proses reinstall dibatalkan.${NC}"
    exit 0
fi

for ((i = 3; i >= 1; i--)); do
    echo "Memulai proses reinstall dalam $i detik... (Ctrl+C untuk membatalkan)"
    sleep 1
done

# ============================================================================
# 1. FUNGSI UNINSTALL BERSIH
# ============================================================================
clean_uninstall() {
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}🧹 1. MELAKUKAN UNINSTALL BERSIH INSTALASI LAMA...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    # Stop dan Disable Layanan GenieACS
    echo -e "${YELLOW}-> Menghentikan layanan GenieACS...${NC}"
    systemctl stop genieacs-{cwmp,fs,ui,nbi} 2>/dev/null || true
    systemctl disable genieacs-{cwmp,fs,ui,nbi} 2>/dev/null || true

    # Hapus file unit systemd
    rm -f /etc/systemd/system/genieacs-*.service
    systemctl daemon-reload

    # Drop Database & Stop MongoDB
    echo -e "${YELLOW}-> Membersihkan database MongoDB GenieACS...${NC}"
    mongosh genieacs --eval "db.dropDatabase()" 2>/dev/null || mongo genieacs --eval "db.dropDatabase()" 2>/dev/null || true
    systemctl stop mongod 2>/dev/null || true
    systemctl disable mongod 2>/dev/null || true

    # Hapus file konfigurasi & direktori GenieACS
    echo -e "${YELLOW}-> Membersihkan berkas dan direktori GenieACS...${NC}"
    rm -rf /opt/genieacs
    rm -rf /var/log/genieacs
    rm -f /etc/logrotate.d/genieacs
    rm -f /usr/bin/genieacs-* /usr/local/bin/genieacs-*

    # Hapus modul global genieacs
    echo -e "${YELLOW}-> Membersihkan modul GenieACS NPM...${NC}"
    NODE_MODULES_DIR=$(npm root -g 2>/dev/null || echo "/usr/lib/node_modules")
    rm -rf "$NODE_MODULES_DIR/genieacs"
    rm -rf /usr/local/lib/node_modules/genieacs

    echo -e "${GREEN}✅ Clean Uninstall selesai.${NC}"
}

# ============================================================================
# 2. FUNGSI INSTALASI NODE.JS 20
# ============================================================================
install_nodejs() {
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}📦 2. MENGINSTAL NODE.JS 20...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    apt-get update -y
    apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release ufw

    mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg 2>/dev/null || true

    if [[ "$UBUNTU_CODENAME" == "focal" ]]; then
        echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x focal main" | tee /etc/apt/sources.list.d/nodesource.list
    else
        echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list
    fi

    apt-get update -y
    apt-get install -y nodejs

    if command -v node &> /dev/null; then
        echo -e "${GREEN}✅ Node.js $(node -v) & NPM $(npm -v) terinstal${NC}"
    else
        echo -e "${RED}❌ Gagal menginstal Node.js${NC}"
        exit 1
    fi
}

# ============================================================================
# 3. FUNGSI INSTALASI MONGODB & DATABASE TOOLS
# ============================================================================
install_mongodb() {
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}🍃 3. MENGINSTAL MONGODB & DATABASE TOOLS...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    if [[ "$UBUNTU_CODENAME" == "focal" ]]; then
        curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-4.4.gpg 2>/dev/null || true
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-4.4.gpg ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list
        apt-get update -y
        apt-get install -y mongodb-org mongodb-org-tools mongodb-database-tools 2>/dev/null || apt-get install -y mongodb-org
    elif [[ "$UBUNTU_CODENAME" == "noble" ]]; then
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg 2>/dev/null || true
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
        apt-get update -y
        apt-get install -y mongodb-org mongodb-database-tools 2>/dev/null || apt-get install -y mongodb-org
    else
        curl -fsSL https://pgp.mongodb.com/server-6.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg 2>/dev/null || true
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
        apt-get update -y
        apt-get install -y mongodb-org mongodb-database-tools 2>/dev/null || apt-get install -y mongodb-org
    fi

    mkdir -p /var/lib/mongodb /var/log/mongodb
    chown -R mongodb:mongodb /var/lib/mongodb /var/log/mongodb 2>/dev/null || true

    systemctl enable --now mongod
    sleep 3

    if systemctl is-active --quiet mongod; then
        echo -e "${GREEN}✅ Layanan MongoDB berhasil berjalan${NC}"
    else
        echo -e "${RED}❌ MongoDB gagal berjalan, mencoba restart...${NC}"
        systemctl restart mongod
    fi
}

# ============================================================================
# 4. FUNGSI INSTALASI GENIEACS BASE
# ============================================================================
install_genieacs() {
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}⚙️ 4. MEMERIKSA & MENGINSTAL GENIEACS BASE TERBARU...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    echo -e "${YELLOW}-> Memeriksa versi terbaru dari GitHub (genieacs/genieacs)...${NC}"
    LATEST_VERSION=$(curl -s https://api.github.com/repos/genieacs/genieacs/releases/latest 2>/dev/null | grep '"tag_name":' | sed -E 's/.*"v?([^"]+)".*/\1/')
    
    if [ -z "$LATEST_VERSION" ]; then
        LATEST_VERSION=$(npm view genieacs version 2>/dev/null || echo "1.2.13")
    fi

    echo -e "${GREEN}🔍 Versi default: v1.2.13 | Versi terbaru GitHub: v${LATEST_VERSION}${NC}"
    
    TARGET_VERSION="1.2.13"
    if [ "$LATEST_VERSION" != "1.2.13" ]; then
        echo -e "${YELLOW}Apakah Anda ingin menginstal versi terbaru GenieACS (v${LATEST_VERSION})? (y/N - default 'n' = v1.2.13):${NC}"
        read -t 15 update_choice || update_choice="n"
        if [[ "$update_choice" =~ ^[Yy]$ ]]; then
            TARGET_VERSION="$LATEST_VERSION"
        fi
    fi

    echo -e "${YELLOW}-> Menginstal GenieACS v${TARGET_VERSION}...${NC}"
    npm install -g "genieacs@${TARGET_VERSION}" --force

    BIN_DIR=$(dirname "$(which genieacs-cwmp 2>/dev/null || echo "/usr/bin/genieacs-cwmp")")
    if [ "$BIN_DIR" != "/usr/bin" ] && [ -f "$BIN_DIR/genieacs-cwmp" ]; then
        ln -sf "$BIN_DIR"/genieacs-* /usr/bin/
    fi

    useradd --system --no-create-home --user-group genieacs 2>/dev/null || true
    mkdir -p /opt/genieacs /opt/genieacs/ext /var/log/genieacs
    
    cat << EOF > /opt/genieacs/genieacs.env
GENIEACS_CWMP_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-cwmp-access.log
GENIEACS_NBI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-nbi-access.log
GENIEACS_FS_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-fs-access.log
GENIEACS_UI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-ui-access.log
GENIEACS_DEBUG_FILE=/var/log/genieacs/genieacs-debug.yaml
GENIEACS_EXT_DIR=/opt/genieacs/ext
GENIEACS_UI_JWT_SECRET=secret
EOF

    chown -R genieacs:genieacs /opt/genieacs /var/log/genieacs
    chmod 600 /opt/genieacs/genieacs.env

    # Systemd Unit Files
    cat << EOF > /etc/systemd/system/genieacs-cwmp.service
[Unit]
Description=GenieACS CWMP
After=network.target

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-cwmp

[Install]
WantedBy=default.target
EOF

    cat << EOF > /etc/systemd/system/genieacs-nbi.service
[Unit]
Description=GenieACS NBI
After=network.target

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-nbi

[Install]
WantedBy=default.target
EOF

    cat << EOF > /etc/systemd/system/genieacs-fs.service
[Unit]
Description=GenieACS FS
After=network.target

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-fs

[Install]
WantedBy=default.target
EOF

    cat << EOF > /etc/systemd/system/genieacs-ui.service
[Unit]
Description=GenieACS UI
After=network.target

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-ui

[Install]
WantedBy=default.target
EOF

    # Logrotate
    cat << EOF > /etc/logrotate.d/genieacs
/var/log/genieacs/*.log /var/log/genieacs/*.yaml {
    daily
    rotate 30
    compress
    delaycompress
    dateext
}
EOF

    systemctl daemon-reload
    systemctl enable --now genieacs-{cwmp,fs,ui,nbi}
    echo -e "${GREEN}✅ GenieACS Base berhasil dikonfigurasi${NC}"
}

# ============================================================================
# 5. FUNGSI PEMASANGAN MULTITAB & RESTORE DATABASE
# ============================================================================
install_multitab_and_restore() {
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}🧩 5. PEMASANGAN GENIEACS MULTITAB & RESTORE DATABASE...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    NODE_MODULES_DIR=$(npm root -g 2>/dev/null || echo "/usr/lib/node_modules")

    if [ -d "$SCRIPT_DIR/genieacs" ]; then
        echo -e "${YELLOW}-> Meng-copy modul GenieACS Multitab...${NC}"
        mkdir -p "$NODE_MODULES_DIR/genieacs"
        cp -r "$SCRIPT_DIR/genieacs/"* "$NODE_MODULES_DIR/genieacs/"
        
        echo -e "${YELLOW}-> Menginstal dependensi modul GenieACS Multitab...${NC}"
        (cd "$NODE_MODULES_DIR/genieacs" && npm install --omit=dev --force)
        echo -e "${GREEN}✅ Multitab module & dependensi terinstal di $NODE_MODULES_DIR/genieacs${NC}"
    else
        echo -e "${RED}⚠️ Direktori '$SCRIPT_DIR/genieacs' tidak ditemukan!${NC}"
    fi

    if [ -d "$SCRIPT_DIR/db" ]; then
        echo -e "${YELLOW}-> Melakukan restore database virtual parameter...${NC}"
        if command -v mongorestore &> /dev/null; then
            mongorestore --db genieacs --drop "$SCRIPT_DIR/db"
            echo -e "${GREEN}✅ Restore database berhasil!${NC}"
        else
            echo -e "${RED}❌ mongorestore tidak ditemukan, menginstal mongodb-database-tools...${NC}"
            apt-get install -y mongodb-database-tools 2>/dev/null || true
            mongorestore --db genieacs --drop "$SCRIPT_DIR/db" 2>/dev/null || true
        fi

        # Auto-update IP Server pada provision 'inform'
        if [ -n "$local_ip" ]; then
            echo -e "${YELLOW}-> Mengatur IP Server otomatis (http://${local_ip}:7547) pada provision 'inform'...${NC}"
            node -e "
            try {
                const { MongoClient } = require('$NODE_MODULES_DIR/genieacs/node_modules/mongodb');
                MongoClient.connect('mongodb://127.0.0.1/genieacs').then(async client => {
                    const db = client.db();
                    const doc = await db.collection('provisions').findOne({_id: 'inform'});
                    if (doc && doc.script) {
                        const newScript = doc.script.replace(/http:\/\/[0-9\.]+:7547/g, 'http://${local_ip}:7547');
                        await db.collection('provisions').updateOne({_id: 'inform'}, {\$set: {script: newScript}});
                        console.log('✅ IP Provision inform otomatis diperbarui ke http://${local_ip}:7547');
                    }
                    await client.close();
                }).catch(() => {});
            } catch (e) {}
            " 2>/dev/null || true
        fi
    else
        echo -e "${RED}⚠️ Direktori '$SCRIPT_DIR/db' tidak ditemukan!${NC}"
    fi

    # Buka Port Firewall UFW
    if command -v ufw &> /dev/null; then
        ufw allow 3000/tcp 2>/dev/null || true
        ufw allow 7547/tcp 2>/dev/null || true
    fi

    # Restart semua layanan GenieACS
    systemctl daemon-reload
    systemctl restart genieacs-{cwmp,fs,ui,nbi}
    sleep 3
}

# ============================================================================
# EKSEKUSI PROSES REINSTALL
# ============================================================================
clean_uninstall
install_nodejs
install_mongodb
install_genieacs
install_multitab_and_restore

# ============================================================================
# VERIFIKASI AKHIR STATUS
# ============================================================================
echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}===================== VERIFIKASI STATUS HILIR ==============================${NC}"
echo -e "${BLUE}============================================================================${NC}"

if systemctl is-active --quiet mongod; then
    echo -e "${GREEN}✅ MongoDB : RUNNING${NC}"
else
    echo -e "${RED}❌ MongoDB : STOPPED${NC}"
fi

if systemctl is-active --quiet genieacs-ui; then
    echo -e "${GREEN}✅ GenieACS UI : RUNNING${NC}"
else
    echo -e "${RED}❌ GenieACS UI : STOPPED${NC}"
fi

if systemctl is-active --quiet genieacs-cwmp; then
    echo -e "${GREEN}✅ GenieACS CWMP : RUNNING${NC}"
else
    echo -e "${RED}❌ GenieACS CWMP : STOPPED${NC}"
fi

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}🎉 PROSES REINSTALL SELESAI!${NC}"
echo -e "${GREEN}👉 Akses GenieACS UI Port 3000 : http://${local_ip}:3000${NC}"
echo -e "${GREEN}============================================================================${NC}"
