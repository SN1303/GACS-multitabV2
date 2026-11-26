#!/usr/bin/env node
/*
 * GENERATOR DEVICE DUMMY untuk GenieACS (HANYA UNTUK SERVER TEST)
 * -----------------------------------------------------------------------------
 * Mengisi MongoDB dengan ONT palsu supaya halaman Overview & Devices terlihat
 * terisi tanpa perlu ONT sungguhan. Setiap device diberi _id berawalan "DUMMY-"
 * dan tag "dummy" agar mudah dihapus.
 *
 * Jalankan DI SERVER GenieACS (butuh Node + modul mongodb bawaan genieacs):
 *   node dummy-devices.js add        # tambah set device dummy (default)
 *   node dummy-devices.js add 40     # tambah ~40 device dummy
 *   node dummy-devices.js clear      # hapus semua device dummy (DUMMY-*)
 *
 * JANGAN jalankan di server produksi.
 */

const path = require('path');
const { execSync } = require('child_process');

let MongoClient;
try {
  const nm = execSync('npm root -g', { encoding: 'utf8' }).trim();
  ({ MongoClient } = require(path.join(nm, 'genieacs', 'node_modules', 'mongodb')));
} catch (e) {
  console.error('Gagal memuat modul mongodb bawaan genieacs. Jalankan di server GenieACS.');
  process.exit(1);
}

const URL = 'mongodb://127.0.0.1/genieacs';
const now = Date.now();
const ms = (d) => new Date(now - d);

// leaf parameter
const P = (value, type = 'xsd:string') => ({ _value: value, _type: type, _timestamp: ms(0), _writable: false });
// object node
const O = (children) => Object.assign({ _object: true, _timestamp: ms(0), _writable: false }, children);

// Daftar model: [jumlah, manufacturer, productClass, oui]
const MODELS = [
  [5, 'ZTE', 'F609', 'D0577B'],
  [4, 'ZTE', 'F670L', 'D0577B'],
  [3, 'ZTE', 'F660', 'D0577B'],
  [2, 'ZTE', 'F673AV9a', 'D0577B'],
  [4, 'Huawei Technologies Co., Ltd', 'HG8546M', '00259E'],
  [3, 'Huawei Technologies Co., Ltd', 'HS8546V5', '00259E'],
  [3, 'FiberHome', 'HG6243C', '001D82'],
  [2, 'MikroTik', 'RouterOS', 'CC2DE0'],
  [2, 'V-SOL', 'XPON+1GE+WIFI', '001E80'],
  [1, 'CDTECH', 'CData-FD511G', '0C8268'],
  [1, 'Nokia', 'G-140W-C', '001AC3'],
];

const SSIDS = ['RT-RW-Net', 'WIFI-Rumah', 'HotSpot-01', 'MyHome', 'Kantor-Net'];
const rint = (a, b) => Math.floor(Math.random() * (b - a + 1)) + a;
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

function makeDevice(mfr, pc, oui, n) {
  const sn = pc.replace(/[^A-Za-z0-9]/g, '').slice(0, 6).toUpperCase() + String(10000 + n).slice(-5);
  const id = `DUMMY-${pc}-${sn}`;
  const mac = Array.from({ length: 6 }, () => rint(0, 255).toString(16).padStart(2, '0')).join(':').toUpperCase();
  const rx = (-18 - Math.random() * 10).toFixed(2);          // -18..-28 dBm
  const temp = String(rint(38, 72));                          // suhu chip
  const clients = String(rint(0, 12));
  const ppp = `user${1000 + n}@isp.net`;
  const wanip = `100.${rint(64, 127)}.${rint(0, 255)}.${rint(1, 254)}`;
  const tr069ip = `10.${rint(0, 255)}.${rint(0, 255)}.${rint(1, 254)}`;
  const online = Math.random() < 0.8;                         // 80% online
  const lastInform = online ? ms(rint(5, 60) * 1000) : ms(rint(2, 72) * 3600 * 1000);
  const ponSerial = mfr.startsWith('ZTE') ? 'ZTEG' + sn : '';

  return {
    _id: id,
    _timestamp: ms(0),
    _lastInform: lastInform,
    _registered: ms(rint(1, 90) * 86400 * 1000),
    _lastBoot: ms(rint(1, 240) * 3600 * 1000),
    _tags: ['dummy'],
    _deviceId: { _Manufacturer: mfr, _OUI: oui, _ProductClass: pc, _SerialNumber: sn },
    InternetGatewayDevice: O({
      DeviceInfo: O({
        Manufacturer: P(mfr),
        ProductClass: P(pc),
        SerialNumber: P(sn),
        HardwareVersion: P('V' + rint(1, 3) + '.0'),
        SoftwareVersion: P('V' + rint(1, 9) + '.0.' + rint(0, 20)),
        UpTime: P(String(rint(3600, 2000000)), 'xsd:unsignedInt'),
      }),
      LANDevice: O({
        1: O({
          WLANConfiguration: O({
            1: O({
              SSID: P(pick(SSIDS) + '-' + rint(1, 99)),
              KeyPassphrase: P('wifi' + rint(10000000, 99999999)),
              TotalAssociations: P(clients, 'xsd:unsignedInt'),
            }),
          }),
        }),
      }),
    }),
    VirtualParameters: O({
      RXPower: P(rx),
      gettemp: P(temp),
      activedevices: P(clients, 'xsd:unsignedInt'),
      pppoeUsername: P(ppp),
      pppoeIP: P(wanip),
      IPTR069: P(tr069ip),
      WlanPassword: P('wifi' + rint(10000000, 99999999)),
      getpppuptime: P(String(rint(60, 2000000)), 'xsd:unsignedInt'),
      getdeviceuptime: P(String(rint(3600, 2000000)), 'xsd:unsignedInt'),
      getSerialNumber: P(sn),
      getPonSerial: P(ponSerial || sn),
      MacAddress: P(mac),
      getponmode: P(pick(['GPON', 'EPON', 'Ethernet'])),
    }),
  };
}

async function main() {
  const mode = process.argv[2] || 'add';
  const client = await MongoClient.connect(URL);
  const col = client.db().collection('devices');

  if (mode === 'clear') {
    const r = await col.deleteMany({ _id: /^DUMMY-/ });
    console.log(`Dihapus ${r.deletedCount} device dummy.`);
    await client.close();
    return;
  }

  // mode add
  const target = parseInt(process.argv[3], 10) || MODELS.reduce((s, m) => s + m[0], 0);
  const docs = [];
  let n = 0;
  outer: for (const [count, mfr, pc, oui] of MODELS) {
    for (let i = 0; i < count; i++) {
      docs.push(makeDevice(mfr, pc, oui, n++));
      if (docs.length >= target) break outer;
    }
  }
  // kalau diminta lebih banyak dari daftar dasar, ulangi secara acak
  while (docs.length < target) {
    const [, mfr, pc, oui] = pick(MODELS);
    docs.push(makeDevice(mfr, pc, oui, n++));
  }

  for (const d of docs) await col.replaceOne({ _id: d._id }, d, { upsert: true });
  console.log(`Berhasil menambah/replace ${docs.length} device dummy.`);
  console.log('Buka UI -> Overview & Devices untuk melihat hasilnya.');
  console.log('Hapus lagi dengan: node dummy-devices.js clear');
  await client.close();
}

main().catch((e) => { console.error('Error:', e.message); process.exit(1); });
