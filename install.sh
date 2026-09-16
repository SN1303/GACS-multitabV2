#!/bin/bash

# ============================================================================
# AUTO INSTALLER GENIEACS MULTITAB V2 (UNIVERSAL: UBUNTU / DEBIAN / ARMBIAN)
# ============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. Cek apakah dijalankan sebagai root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Harap jalankan script ini sebagai root (sudo bash install.sh)${NC}"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Dapatkan IP lokal dan info sistem
local_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$local_ip" ]; then
    local_ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
fi

DISTRO_ID=$(lsb_release -is 2>/dev/null || echo "Linux")
DISTRO_VERSION=$(lsb_release -rs 2>/dev/null || echo "Unknown")
DISTRO_CODENAME=$(lsb_release -cs 2>/dev/null || echo "Unknown")
ARCH=$(uname -m)

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}==================  AUTOINSTALL GACS MULTITAB V2  ==========================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}==================  KKK   KKK   NNNN    NNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}==================  KKK  KKK    NNNNN   NNN   SS          ==================${NC}"
echo -e "${GREEN}==================  KKKKKKK     NNN NN  NNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}==================  KKK  KKK    NNN  NN NNN           SS  ==================${NC}"
echo -e "${GREEN}==================  KKK   KKK   NNN   NNNNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}OS System    : ${DISTRO_ID} ${DISTRO_VERSION} (${DISTRO_CODENAME}) - Arch: ${ARCH}${NC}"
echo -e "${GREEN}IP Server    : ${local_ip}${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${YELLOW} Apakah anda ingin melanjutkan instalasi GenieACS Multitab? (y/n)${NC}"
read confirmation

if [ "$confirmation" != "y" ]; then
    echo -e "${YELLOW}Instalasi dibatalkan. Tidak ada perubahan pada sistem anda.${NC}"
    exit 0
fi

for ((i = 3; i >= 1; i--)); do
    echo "Melanjutkan dalam $i detik... Tekan Ctrl+C untuk membatalkan"
    sleep 1
done

# ============================================================================
# 1. INSTALL NODE.JS 20
# ============================================================================
install_nodejs() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}📦 [1/4] Menginstal Node.js 20 LTS...${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    
    # Bersihkan instalasi Node.js lama jika bermasalah
    apt-get remove --purge -y nodejs npm nodejs-doc libnode-dev 2>/dev/null || true
    rm -rf /etc/apt/sources.list.d/nodesource.list* /var/lib/apt/lists/*
    
    apt-get update -y
    apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release wget ufw

    mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg 2>/dev/null || true

    if [[ "$DISTRO_CODENAME" == "focal" ]]; then
        echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x focal main" | tee /etc/apt/sources.list.d/nodesource.list
    else
        echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list
    fi

    apt-get update -y
    apt-get install -y nodejs

    if command -v node &> /dev/null && command -v npm &> /dev/null; then
        echo -e "${GREEN}✅ Node.js $(node -v) dan NPM $(npm -v) berhasil terinstal.${NC}"
    else
        echo -e "${YELLOW}Mencoba instalasi alternatif Node.js via NVM...${NC}"
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        nvm install 20
        nvm use 20
        ln -sf "$NVM_DIR/versions/node/$(nvm version)/bin/node" /usr/bin/node 2>/dev/null || true
        ln -sf "$NVM_DIR/versions/node/$(nvm version)/bin/npm" /usr/bin/npm 2>/dev/null || true
    fi
}

# ============================================================================
# 2. INSTALL MONGODB & DATABASE TOOLS
# ============================================================================
install_mongodb_docker() {
    echo -e "${YELLOW}-> Menginstal MongoDB via Docker (Fallback Armbian/Arch)...${NC}"
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker
    fi
    docker rm -f mongodb 2>/dev/null || true
    docker run -d --name mongodb \
        --restart unless-stopped \
        -p 27017:27017 \
        -v mongodb_data:/data/db \
        mongo:5.0
    sleep 5
}

install_mongodb() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}🍃 [2/4] Menginstal MongoDB & Database Tools...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    systemctl stop mongod 2>/dev/null || true
    rm -f /etc/apt/sources.list.d/mongodb-*.list

    apt-get update -y
    apt-get install -y gnupg curl wget

    if [[ "$DISTRO_CODENAME" == "focal" ]]; then
        curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-4.4.gpg 2>/dev/null || true
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-4.4.gpg ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list
        apt-get update -y
        apt-get install -y mongodb-org mongodb-org-tools mongodb-database-tools 2>/dev/null || apt-get install -y mongodb-org
    else
        curl -fsSL https://pgp.mongodb.com/server-6.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg 2>/dev/null || true
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
        apt-get update -y
        apt-get install -y mongodb-org mongodb-database-tools 2>/dev/null || apt-get install -y mongodb-org
    fi

    mkdir -p /var/lib/mongodb /var/log/mongodb
    chown -R mongodb:mongodb /var/lib/mongodb /var/log/mongodb 2>/dev/null || true
    systemctl enable --now mongod 2>/dev/null || true
    sleep 3

    if systemctl is-active --quiet mongod 2>/dev/null; then
        echo -e "${GREEN}✅ MongoDB Native berhasil berjalan.${NC}"
    else
        echo -e "${YELLOW}MongoDB native tidak dapat dimulai, beralih ke container Docker...${NC}"
        install_mongodb_docker
    fi
}

# ============================================================================
# 3. INSTALL GENIEACS SERVICE BASE
# ============================================================================
install_genieacs() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}⚙️  [3/4] Menginstal Layanan GenieACS & Konfigurasi...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    TARGET_VERSION="1.2.13"
    LATEST_VERSION=$(curl -s https://api.github.com/repos/genieacs/genieacs/releases/latest 2>/dev/null | grep '"tag_name":' | sed -E 's/.*"v?([^"]+)".*/\1/')
    if [ -n "$LATEST_VERSION" ] && [ "$LATEST_VERSION" != "1.2.13" ]; then
        echo -e "${YELLOW}Apakah ingin menginstal GenieACS versi terbaru (v${LATEST_VERSION})? (y/N - default: v1.2.13):${NC}"
        read -t 15 update_choice || update_choice="n"
        if [[ "$update_choice" =~ ^[Yy]$ ]]; then
            TARGET_VERSION="$LATEST_VERSION"
        fi
    fi

    echo -e "${YELLOW}-> Menginstal GenieACS v${TARGET_VERSION} via NPM...${NC}"
    npm install -g "genieacs@${TARGET_VERSION}" --force

    BIN_DIR=$(dirname "$(which genieacs-cwmp 2>/dev/null || echo "/usr/bin/genieacs-cwmp")")
    if [ "$BIN_DIR" != "/usr/bin" ] && [ -f "$BIN_DIR/genieacs-cwmp" ]; then
        ln -sf "$BIN_DIR"/genieacs-* /usr/bin/
    fi

    useradd --system --no-create-home --user-group genieacs 2>/dev/null || true
    mkdir -p /opt/genieacs /opt/genieacs/ext /var/log/genieacs
    chown -R genieacs:genieacs /opt/genieacs /var/log/genieacs

    cat << EOF > /opt/genieacs/genieacs.env
GENIEACS_CWMP_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-cwmp-access.log
GENIEACS_NBI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-nbi-access.log
GENIEACS_FS_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-fs-access.log
GENIEACS_UI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-ui-access.log
GENIEACS_DEBUG_FILE=/var/log/genieacs/genieacs-debug.yaml
GENIEACS_EXT_DIR=/opt/genieacs/ext
GENIEACS_UI_JWT_SECRET=secret
EOF
    chown genieacs:genieacs /opt/genieacs/genieacs.env
    chmod 600 /opt/genieacs/genieacs.env

    # Systemd Unit Files
    for service in cwmp nbi fs ui; do
        cat << EOF > /etc/systemd/system/genieacs-${service}.service
[Unit]
Description=GenieACS ${service^^}
After=network.target

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-${service}

[Install]
WantedBy=default.target
EOF
    done

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
    echo -e "${GREEN}✅ Layanan GenieACS berhasil dikonfigurasi & diaktifkan.${NC}"
}

# ============================================================================
# 4. PASANG MODUL MULTITAB, RESTORE DB, & AUTO-SET IP INFORM
# ============================================================================
install_multitab_and_restore() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${YELLOW}🎛️  [4/4] Memasang Multitab V2, Restore Database, & Konfigurasi IP...${NC}"
    echo -e "${BLUE}============================================================================${NC}"

    NODE_MODULES_DIR=$(npm root -g 2>/dev/null || echo "/usr/lib/node_modules")

    if [ -d "$SCRIPT_DIR/genieacs" ]; then
        echo -e "${YELLOW}-> Meng-copy paket GenieACS Multitab ke $NODE_MODULES_DIR/genieacs...${NC}"
        cp -r "$SCRIPT_DIR/genieacs" "$NODE_MODULES_DIR/"
        (cd "$NODE_MODULES_DIR/genieacs" && npm install --omit=dev --force 2>/dev/null || true)
        echo -e "${GREEN}✅ Modul Multitab terpasang.${NC}"
    fi

    if [ -d "$SCRIPT_DIR/db" ]; then
        echo -e "${YELLOW}-> Melakukan restore database MongoDB GenieACS...${NC}"
        if ! command -v mongorestore &> /dev/null; then
            apt-get install -y mongodb-database-tools 2>/dev/null || true
        fi

        if command -v mongorestore &> /dev/null; then
            mongorestore --db genieacs --drop "$SCRIPT_DIR/db"
            echo -e "${GREEN}✅ Restore database multitab berhasil!${NC}"
        else
            echo -e "${RED}⚠️  mongorestore tidak ditemukan. Melewati restore DB otomatis.${NC}"
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
                        await db.collection('provisions').updateOne({_id: 'inform'}, { \$set: { script: newScript } });
                        console.log('✅ IP Provision inform otomatis diperbarui ke http://${local_ip}:7547');
                    }
                    await client.close();
                }).catch((e) => { console.log('Gagal konek mongo:', e.message); });
            } catch (e) {
                console.log('Catched:', e.message);
            }
            " 2>/dev/null || true
        fi
    fi

    # Buka firewall UFW jika aktif
    if command -v ufw &> /dev/null; then
        ufw allow 3000/tcp 2>/dev/null || true
        ufw allow 7547/tcp 2>/dev/null || true
    fi

    systemctl daemon-reload
    systemctl restart genieacs-{cwmp,fs,ui,nbi}
    echo -e "${GREEN}✅ Semua layanan GenieACS berhasil direstart.${NC}"
}

# ============================================================================
# EKSEKUSI ALUR
# ============================================================================
if ! command -v node &> /dev/null; then
    install_nodejs
fi

if ! systemctl is-active --quiet mongod 2>/dev/null && ! docker ps 2>/dev/null | grep -q mongodb; then
    install_mongodb
fi

if ! systemctl is-active --quiet genieacs-cwmp 2>/dev/null; then
    install_genieacs
fi

install_multitab_and_restore

# ============================================================================
# STATUS AKHIR
# ============================================================================
echo -e "\n${BLUE}============================================================================${NC}"
echo -e "${BLUE}=========================== STATUS INSTALASI ===============================${NC}"
echo -e "${BLUE}============================================================================${NC}"
if systemctl is-active --quiet mongod 2>/dev/null || docker ps 2>/dev/null | grep -q mongodb; then
    echo -e "${GREEN}✅ Database MongoDB    : BERJALAN${NC}"
else
    echo -e "${RED}❌ Database MongoDB    : BERHENTI${NC}"
fi

for s in cwmp ui nbi fs; do
    if systemctl is-active --quiet genieacs-${s} 2>/dev/null; then
        echo -e "${GREEN}✅ GenieACS ${s^^}        : BERJALAN${NC}"
    else
        echo -e "${RED}❌ GenieACS ${s^^}        : BERHENTI${NC}"
    fi
done

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN} Web UI GenieACS  : http://${local_ip}:3000${NC}"
echo -e "${GREEN} TR-069 CWMP URL  : http://${local_ip}:7547${NC}"
echo -e "${GREEN} Login Default    : admin / admin${NC}"
echo -e "${GREEN}============================================================================${NC}"
