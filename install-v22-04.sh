GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Cek apakah dijalankan sebagai root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Harap jalankan script ini sebagai root (sudo bash install-v22-04.sh)${NC}"
    exit 1
fi

# Dapatkan lokasi direktori script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Dapatkan IP lokal dan info sistem
local_ip=$(hostname -I | awk '{print $1}')
UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || echo "Unknown")
UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "Unknown")
ARCH=$(uname -m)

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}==================  INSTALASI GACS - UBUNTU ${UBUNTU_VERSION} (${UBUNTU_CODENAME}) ==================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}==================  KKK   KKK   NNNN    NNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}==================  KKK  KKK    NNNNN   NNN   SS          ==================${NC}"
echo -e "${GREEN}==================  KKKKKKK     NNN NN  NNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}==================  KKK  KKK    NNN  NN NNN           SS  ==================${NC}"
echo -e "${GREEN}==================  KKK   KKK   NNN   NNNNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}========================= . Info 0812-3456-7890  ===========================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}${NC}"
echo -e "${GREEN}Autoinstall GenieACS.${NC}"
echo -e "${GREEN}${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${RED}${NC}"
echo -e "${GREEN} Apakah anda ingin melanjutkan? (y/n)${NC}"
read confirmation

if [ "$confirmation" != "y" ]; then
    echo -e "${GREEN}Install dibatalkan. Tidak ada perubahan dalam ubuntu server anda.${NC}"
    exit 1
fi
for ((i = 5; i >= 1; i--)); do
	sleep 1
    echo "Melanjutkan dalam $i. Tekan ctrl+c untuk membatalkan"
done

echo -e "${YELLOW}Memulai instalasi GenieACS...${NC}"

# Fungsi untuk menginstal Node.js
install_nodejs() {
    echo -e "${YELLOW}Menginstal Node.js...${NC}"
    
    # Hapus instalasi Node.js lama yang bermasalah
    echo -e "${YELLOW}Membersihkan instalasi Node.js lama...${NC}"
    apt-get remove --purge -y nodejs npm nodejs-doc libnode-dev 2>/dev/null || true
    rm -rf /etc/apt/sources.list.d/nodesource.list* \
           /usr/lib/node_modules \
           /var/lib/apt/lists/* \
           /var/cache/apt/archives/*.deb \
           ~/.npm
    
    # Update package list
    echo -e "${YELLOW}Memperbarui daftar paket...${NC}"
    apt-get update -y
    
    # Install dependencies yang diperlukan
    echo -e "${YELLOW}Menginstal dependensi yang diperlukan...${NC}"
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Tambahkan repository NodeSource
    echo -e "${YELLOW}Menambahkan repository NodeSource...${NC}"
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
    
    # Gunakan repository yang sesuai dengan versi Ubuntu
    if [[ "$UBUNTU_CODENAME" == "focal" ]]; then
        echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x focal main" | tee /etc/apt/sources.list.d/nodesource.list
    else
        echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list
    fi
    
    # Update package list lagi
    echo -e "${YELLOW}Memperbarui daftar paket...${NC}"
    apt-get update -y
    
    # Install Node.js
    echo -e "${YELLOW}Menginstal Node.js 20...${NC}"
    apt-get install -y nodejs
    
    # Verifikasi instalasi
    if command -v node &> /dev/null && command -v npm &> /dev/null; then
        echo -e "${GREEN}✅ Node.js $(node -v) dan NPM $(npm -v) berhasil diinstal${NC}"
    else
        echo -e "${RED}❌ Gagal menginstal Node.js${NC}"
        echo -e "${YELLOW}Mencoba metode alternatif...${NC}"
        install_nodejs_alternative
    fi
}

# Fungsi alternatif untuk menginstal Node.js
install_nodejs_alternative() {
    echo -e "${YELLOW}Menginstal Node.js menggunakan nvm...${NC}"
    
    # Install nvm
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
    
    # Load nvm
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    # Install Node.js menggunakan nvm
    nvm install 20
    nvm use 20
    
    # Buat symlink global
    ln -sf "$NVM_DIR/versions/node/$(nvm version)/bin/node" /usr/local/bin/node
    ln -sf "$NVM_DIR/versions/node/$(nvm version)/bin/npm" /usr/local/bin/npm
    ln -sf "$NVM_DIR/versions/node/$(nvm version)/bin/node" /usr/bin/node 2>/dev/null || true
    ln -sf "$NVM_DIR/versions/node/$(nvm version)/bin/npm" /usr/bin/npm 2>/dev/null || true
    
    if command -v node &> /dev/null && command -v npm &> /dev/null; then
        echo -e "${GREEN}✅ Node.js $(node -v) dan NPM $(npm -v) berhasil diinstal menggunakan nvm${NC}"
    else
        echo -e "${RED}❌ Gagal menginstal Node.js menggunakan nvm${NC}"
        exit 1
    fi
}

# Panggil fungsi install Node.js
install_nodejs

# Fungsi untuk menginstal MongoDB
install_mongodb() {
    echo -e "${YELLOW}Menginstal MongoDB...${NC}"
    
    # Hapus instalasi lama
    systemctl stop mongod 2>/dev/null || true
    apt-get remove --purge -y mongodb* 2>/dev/null || true
    rm -rf /var/lib/mongodb
    rm -rf /var/log/mongodb
    rm -f /etc/apt/sources.list.d/mongodb-*.list
    rm -f /usr/share/keyrings/mongodb-*.gpg

    # Install dependencies
    apt-get update
    apt-get install -y gnupg curl wget

    # Tentukan versi MongoDB yang akan diinstal berdasarkan versi Ubuntu
    if [[ "$UBUNTU_CODENAME" == "focal" ]]; then
        # Untuk Ubuntu 20.04, gunakan MongoDB 4.4
        echo -e "${YELLOW}Menggunakan MongoDB 4.4 untuk Ubuntu 20.04 (Focal)${NC}"
        
        # Tambahkan kunci GPG MongoDB 4.4
        curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-4.4.gpg
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-4.4.gpg ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list
        
        apt-get update
        echo -e "${YELLOW}Menginstal MongoDB 4.4.8...${NC}"
        apt-get install -y mongodb-org=4.4.8 mongodb-org-server=4.4.8 mongodb-org-shell=4.4.8 mongodb-org-mongos=4.4.8 mongodb-org-tools=4.4.8
        
    else
        # Untuk Ubuntu 22.04/24.04, gunakan MongoDB 6.0
        echo -e "${YELLOW}Menggunakan MongoDB 6.0 untuk Ubuntu ${UBUNTU_VERSION} (${UBUNTU_CODENAME})${NC}"
        
        # Tambahkan kunci GPG MongoDB 6.0
        curl -fsSL https://pgp.mongodb.com/server-6.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
        
        apt-get update
        echo -e "${YELLOW}Menginstal MongoDB 6.0...${NC}"
        apt-get install -y mongodb-org mongodb-database-tools || apt-get install -y mongodb-org
    fi

    # Konfigurasi MongoDB
    mkdir -p /var/lib/mongodb
    mkdir -p /var/log/mongodb
    chown -R mongodb:mongodb /var/lib/mongodb
    chown -R mongodb:mongodb /var/log/mongodb

    # Start dan enable MongoDB
    echo -e "${YELLOW}Menjalankan layanan MongoDB...${NC}"
    systemctl enable --now mongod
    
    # Tunggu sebentar agar MongoDB sempat start
    sleep 5
    
    # Cek status MongoDB
    if systemctl is-active --quiet mongod; then
        echo -e "${GREEN}✅ MongoDB berhasil dijalankan${NC}"
        # Cek apakah mongosh sudah terinstall
        if command -v mongosh &> /dev/null; then
            mongosh --eval 'db.runCommand({ connectionStatus: 1 })'
        elif command -v mongo &> /dev/null; then
            mongo --eval 'db.runCommand({ connectionStatus: 1 })'
        else
            echo -e "${YELLOW}⚠️  MongoDB shell (mongosh) tidak ditemukan. Menginstal mongosh...${NC}"
            if [[ "$UBUNTU_CODENAME" == "focal" ]]; then
                # Untuk Ubuntu 20.04
                curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg
                echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
            else
                # Untuk Ubuntu 22.04/24.04
                curl -fsSL https://pgp.mongodb.com/server-6.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg
                echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
            fi
            
            apt-get update
            apt-get install -y mongodb-mongosh
            
            if command -v mongosh &> /dev/null; then
                echo -e "${GREEN}✅ MongoDB Shell (mongosh) berhasil diinstal${NC}"
                mongosh --eval 'db.runCommand({ connectionStatus: 1 })'
            else
                echo -e "${YELLOW}⚠️  Gagal menginstal MongoDB Shell, tetapi instalasi dapat dilanjutkan${NC}"
                echo -e "${YELLOW}   Anda dapat menginstalnya nanti dengan perintah: apt install mongodb-mongosh${NC}"
            fi
        fi
    else
        echo -e "${RED}❌ Gagal menjalankan MongoDB, mencoba metode alternatif...${NC}"
        install_mongodb_docker
    fi
}

# Fungsi untuk menginstal MongoDB menggunakan Docker
install_mongodb_docker() {
    echo -e "${YELLOW}Menginstal MongoDB menggunakan Docker...${NC}"
    
    # Install Docker jika belum terpasang
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Menginstal Docker...${NC}"
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker
    fi
    
    # Hapus container MongoDB lama jika ada
    docker rm -f mongodb 2>/dev/null || true
    
    # Jalankan MongoDB dalam container
    echo -e "${YELLOW}Menjalankan MongoDB dalam container...${NC}"
    docker run -d --name mongodb \
        --restart unless-stopped \
        -p 27017:27017 \
        -v mongodb_data:/data/db \
        -e MONGO_INITDB_ROOT_USERNAME=admin \
        -e MONGO_INITDB_ROOT_PASSWORD=password \
        mongo:6.0
    
    # Tunggu sebentar
    sleep 5
    
    # Verifikasi
    if docker ps | grep -q mongodb; then
        echo -e "${GREEN}✅ MongoDB berjalan dalam container Docker${NC}"
        echo -e "${YELLOW}Info Koneksi MongoDB:${NC}"
        echo -e "- Host: localhost:27017"
        echo -e "- Username: admin"
        echo -e "- Password: password"
    else
        echo -e "${RED}❌ Gagal menjalankan MongoDB dalam container${NC}"
        exit 1
    fi
}

# Panggil fungsi install MongoDB
install_mongodb

# GenieACS
if ! systemctl is-active --quiet genieacs-{cwmp,fs,ui,nbi}; then
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
    
    # Pastikan biner genieacs dapat diakses dari /usr/bin
    BIN_DIR=$(dirname "$(which genieacs-cwmp 2>/dev/null || echo "/usr/bin/genieacs-cwmp")")
    if [ "$BIN_DIR" != "/usr/bin" ] && [ -f "$BIN_DIR/genieacs-cwmp" ]; then
        ln -sf "$BIN_DIR"/genieacs-* /usr/bin/
    fi

    useradd --system --no-create-home --user-group genieacs 2>/dev/null || true
    mkdir -p /opt/genieacs
    mkdir -p /opt/genieacs/ext
    chown -R genieacs:genieacs /opt/genieacs/ext
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
    chown -R genieacs:genieacs /opt/genieacs
    chmod 600 /opt/genieacs/genieacs.env
    mkdir -p /var/log/genieacs
    chown -R genieacs:genieacs /var/log/genieacs

    # create systemd unit files
## CWMP
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

## NBI
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

## FS
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

## UI
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

# config logrotate
    cat << EOF > /etc/logrotate.d/genieacs
/var/log/genieacs/*.log /var/log/genieacs/*.yaml {
    daily
    rotate 30
    compress
    delaycompress
    dateext
}
EOF
    echo -e "${GREEN}========== Install APP GenieACS selesai... ==============${NC}"
    systemctl daemon-reload
    systemctl enable --now genieacs-{cwmp,fs,ui,nbi}
    systemctl start genieacs-{cwmp,fs,ui,nbi}    
    echo -e "${GREEN}================== Sukses genieACS CWMP, FS, NBI, UI ==================${NC}"
else
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}=================== GenieACS sudah terinstall sebelumnya. ==================${NC}"
fi

# Pemasangan Multitab dan Restore DB
NODE_MODULES_DIR=$(npm root -g 2>/dev/null || echo "/usr/lib/node_modules")

if [ -d "$SCRIPT_DIR/genieacs" ]; then
    echo -e "${YELLOW}Meng-copy modul GenieACS Multitab...${NC}"
    cp -r "$SCRIPT_DIR/genieacs" "$NODE_MODULES_DIR/"
    (cd "$NODE_MODULES_DIR/genieacs" && npm install --omit=dev --force 2>/dev/null || true)
    
    if [ -n "$TARGET_VERSION" ]; then
        node -e "
        try {
            const fs = require('fs');
            const path = require('path');
            const targetDir = '$NODE_MODULES_DIR/genieacs';
            const files = ['bin/genieacs-ui', 'bin/genieacs-cwmp', 'bin/genieacs-fs', 'bin/genieacs-nbi', 'public/app.js', 'package.json'];
            files.forEach(f => {
                const p = path.join(targetDir, f);
                if (fs.existsSync(p)) {
                    let str = fs.readFileSync(p, 'utf8');
                    str = str.replace(/1\.2\.[0-9]+(\+[0-9]+)?/g, '$TARGET_VERSION');
                    fs.writeFileSync(p, str);
                }
            });
        } catch(e){}
        " 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ Multitab berhasil di-copy ke $NODE_MODULES_DIR/genieacs${NC}"
else
    echo -e "${RED}⚠️  Direktori '$SCRIPT_DIR/genieacs' tidak ditemukan!${NC}"
fi

if [ -d "$SCRIPT_DIR/db" ]; then
    echo -e "${YELLOW}Melakukan restore database virtual parameter...${NC}"
    if command -v mongorestore &> /dev/null; then
        mongorestore --db genieacs --drop "$SCRIPT_DIR/db"
        echo -e "${GREEN}✅ Restore database berhasil!${NC}"
    else
        echo -e "${RED}⚠️  mongorestore tidak ditemukan. Menginstal mongodb-database-tools...${NC}"
        apt-get install -y mongodb-database-tools 2>/dev/null || true
        if command -v mongorestore &> /dev/null; then
            mongorestore --db genieacs --drop "$SCRIPT_DIR/db"
            echo -e "${GREEN}✅ Restore database berhasil!${NC}"
        else
            echo -e "${RED}❌ Gagal melakukan restore DB, mongorestore belum terinstal.${NC}"
        fi
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
    echo -e "${RED}⚠️  Direktori '$SCRIPT_DIR/db' tidak ditemukan!${NC}"
fi

systemctl daemon-reload
systemctl restart genieacs-{cwmp,fs,ui,nbi}

# Sukses
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}============ GACS UI akses port 3000 : http://$local_ip:3000 ==============${NC}"
echo -e "${GREEN}=================== Informasi: Whatsapp 081234567890 =======================${NC}"
echo -e "${GREEN}============================================================================${NC}"
