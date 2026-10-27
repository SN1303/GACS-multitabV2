import fs from 'fs';
import path from 'path';

/**
 * WaLidStore
 * Menyimpan pemetaan JID (@lid atau @s.whatsapp.net) -> Tag / Nomor HP / PPPoE Username
 * Mengikuti implementasi D:\billing-rtrw-radius\services\waLidStore.js
 */
export class WaLidStore {
  constructor(filePath) {
    this.filePath = filePath;
    this.map = Object.create(null);
    this._load();
  }

  _load() {
    try {
      if (fs.existsSync(this.filePath)) {
        const raw = JSON.parse(fs.readFileSync(this.filePath, 'utf8'));
        this.map = raw && typeof raw === 'object' ? raw : Object.create(null);
      }
    } catch (e) {
      this.map = Object.create(null);
    }
  }

  _save() {
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.filePath, JSON.stringify(this.map, null, 2), 'utf8');
    } catch (_) {}
  }

  get(jid) {
    if (!jid || typeof jid !== 'string') return null;
    const v = this.map[jid.toLowerCase()];
    return v != null ? String(v) : null;
  }

  set(jid, canonicalTag) {
    if (!jid || canonicalTag == null || canonicalTag === '') return;
    this.map[jid.toLowerCase()] = String(canonicalTag);
    this._save();
  }

  /** Cari JID berdasarkan tag (reverse lookup) */
  getByTag(canonicalTag) {
    if (!canonicalTag) return null;
    const target = String(canonicalTag).toLowerCase();
    for (const [jid, tag] of Object.entries(this.map)) {
      if (String(tag).toLowerCase() === target) {
        return jid;
      }
    }
    return null;
  }

  getAll() {
    return { ...this.map };
  }
}

export default WaLidStore;
