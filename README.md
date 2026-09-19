# cfm — Camoufox Manager

Terminal UI + CLI untuk mengelola banyak profil browser **Camoufox** dengan fingerprint
yang berbeda dan konsisten, masing-masing dengan proxy sendiri.

Dibuat untuk kebutuhan akun berskala (akun farm), di mana tiap akun harus terlihat
seperti perangkat yang berbeda tanpa saling membocorkan identitas.

## Kenapa Camoufox

Dolphin Anty dan GoLogin menyamarkan fingerprint hanya di lapisan JavaScript. Nilai
seperti WebGL vendor/renderer, AudioContext, Canvas noise, dan ClientRects tetap
**identik** antar profil. Camoufox menyamarkan di lapisan C++/engine Gecko, sehingga
nilai-nilai itu benar-benar berbeda per profil.

## Fitur

- **1 profil = 1 fingerprint permanen**, dipilih sekali dari 123 preset perangkat nyata
  (macOS 30, Windows 75, Linux 18) dan dipakai terus.
- **Satu proxy per profil**, tersimpan sebagai default; bisa diganti kapan saja.
- **Cookie & login persisten** — profil tetap login setelah browser ditutup.
- **TUI pakai tombol panah** + slash command (`/new`, `/run`, `/proxy`, `/list`, ...).
- **Fullscreen otomatis** di monitor landscape (KWin/X11).
- **Verifikasi geometri** (`cfox-verify`) untuk mendeteksi kombinasi mustahil.

## Instalasi

Butuh Python 3.10+ dan Camoufox.

```bash
# 1. venv + Camoufox (termasuk database GeoIP untuk pencocokan IP)
python3 -m venv ~/.camoufox-venv
~/.camoufox-venv/bin/pip install "camoufox[geoip]" prompt_toolkit questionary
~/.camoufox-venv/bin/camoufox fetch

# 2. script
mkdir -p ~/.local/bin
cp bin/* ~/.local/bin/
chmod +x ~/.local/bin/*

# 3. shebang disesuaikan ke venv (opsional tapi disarankan)
sed -i "1s|.*|#!$HOME/.camoufox-venv/bin/python|" ~/.local/bin/cfox ~/.local/bin/cfm
```

> `cfox` dan `cfm` memakai `#!/usr/bin/env python3` secara default. Kalau pakai venv,
> ganti shebang-nya seperti langkah 3 supaya modul `camoufox` terbaca.

Instalasi Camoufox default ada di `~/.cache/camoufox`, **yang dianggap sekali pakai
oleh sistem**. Script di repo ini secara sengaja memindahkannya ke
`~/.local/share/camoufox` lewat `XDG_CACHE_HOME`, karena `rm -rf ~/.cache/*` (perintah
bersih-bersih yang lazim) akan menghapus instalasi ~1.3 GB tersebut. Ubah lokasinya
dengan env `CAMOUFOX_HOME`.

## Pemakaian

```bash
cfm                     # buka TUI
```

Perintah di dalam TUI:

| Perintah | Fungsi |
|---|---|
| `/new <nama>` | buat profil baru (wizard: OS → proxy) |
| `/run <nama>` | jalankan profil; proxy selalu ditanyakan dengan opsi `★ DEFAULT` |
| `/list` | daftar semua profil |
| `/proxy <nama>` | ganti proxy default profil |
| `/proxies` | status semua proxy; `--test` untuk tes IP keluar |
| `/info <nama>` | detail UA/GPU/screen/cores profil |
| `/newfp <nama>` | ganti fingerprint (profil & proxy tetap) |
| `/newname <lama> <baru>` | ganti nama profil |
| `/rm <nama>` | hapus profil |

Tab menyelesaikan perintah, panah atas/bawah membuka riwayat.

### Langsung lewat CLI

```bash
cfox acc1                        # jalan pakai proxy default profil
cfox acc1 --port 1091            # paksa proxy tertentu
cfox acc1 --port 1091 --headless # tanpa window
cfox acc1 --no-fs                # tanpa fullscreen otomatis
cfox --list                      # daftar profil
cfox acc1 --show                 # lihat identitas tersimpan
cfox acc1 --new                  # regenerate fingerprint
```

### Verifikasi geometri

```bash
cfox-verify acc1 acc2 acc3
```

Membuka tiap profil sebentar dan memeriksa invariant:

```
outer <= avail <= screen
inner <= outer
clientHeight == innerHeight
chrome > 0
```

`window` yang lebih tinggi daripada layar (`outer > avail`) adalah geometri mustahil
yang mudah ditandai detektor. `cfox` menghitung sendiri seluruh nilai `screen.*` dan
`window.*` untuk mencegahnya.

## Proxy

Repo ini tidak mengikatkan diri ke penyedia proxy tertentu. `cfm` membaca port dari
berkas konfigurasi wireproxy dan menampilkannya sebagai pilihan:

```
~/surfshark-proxy/configs/*.conf     # satu .conf per port
```

Format yang dibaca (hanya dua baris ini):

```ini
[Socks5]
BindAddress = 127.0.0.1:1091
```

`ss-up` menyalakan semua config, `ss-down` mematikannya, `cekproxy` menampilkan status
beserta lokasi IP keluarnya.

Untuk proxy HTTP/SOCKS biasa, cukup ubah `cfox` pada bagian `kw["proxy"]`.

## Systemd (opsional)

Agar proxy otomatis menyala saat boot:

```bash
cp systemd/surfshark-proxy.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now surfshark-proxy.service
loginctl enable-linger "$USER"
```

## Catatan penting

- **Jangan menaruh instalasi Camoufox di `~/.cache`.** Direktori itu dianggap sekali
  pakai; `rm -rf ~/.cache/*` akan menghapusnya (pernah terjadi, ~1.3 GB hilang).
- **`fingerprint_preset` membuat `window=` diabaikan.** Camoufox memakai `from_preset()`
  yang mengisi `screen.*` tetapi tidak `window.*`, sehingga `window` dibuat sendiri tanpa
  pembatas. Karena itu `cfox` mengirim `config=window_geometry(...)` secara eksplisit.
  Menulis `window.*` otomatis mematikan seluruh auto-clamp Camoufox, jadi semua batas
  dihitung manual.
- **`no_viewport=True` wajib.** Tanpa itu Playwright memaksa viewport 1280x720 dan
  halaman hanya mengisi pojok kiri-atas meski jendela sudah fullscreen.
- **Penyedia proxy komersial selalu terdaftar di PBL Spamhaus** (`127.0.0.11`). Itu bukan
  tanda spam — IP rumah biasa juga terdaftar. Yang penting: `outer <= screen` tetap benar.
- **Skala.** Pool preset terbatas (macOS 27 valid, Linux 17, Windows 70). Di atas jumlah
  itu preset akan terpakai ulang.

## Lisensi

MIT — lihat [LICENSE](LICENSE).