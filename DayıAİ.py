import random
import sys
import os
import shelve
import re

# Türkçe karakter filtresi
TURKCE_PATTERN = re.compile(r'^[a-züğışçöâîûı]+$')

# ── Dosya yolları ──
VERI_DOSYASI  = "veri.txt"
HAFIZA_DB     = "hafiza"          # shelve → hafiza.db / hafiza.dir / hafiza.bak oluşturur
CHUNK_SATIR   = 50_000            # Kaç satırda bir ilerleme gösterelim

# ══════════════════════════════════════════════════════════════
#  SINIF
# ══════════════════════════════════════════════════════════════
class BasitZeka:
    """
    Disk-backed Markov zinciri (trigram + bigram fallback).
    Hafıza Python shelve ile tutulur — tüm veri RAM'e alınmaz.
    """

    def __init__(self):
        self._db = None
        self._ac()

    # ──────────────────────────────────────────
    # Shelve Yönetimi
    # ──────────────────────────────────────────
    def _ac(self):
        if self._db is None:
            self._db = shelve.open(HAFIZA_DB, flag="c", writeback=False)

    def kapat(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    # ── Anahtar yardımcıları ────────────────────────────────
    @staticmethod
    def _tri_key(k1: str, k2: str) -> str:
        return f"t\x00{k1}\x00{k2}"

    @staticmethod
    def _bi_key(k: str) -> str:
        return f"b\x00{k}"

    @staticmethod
    def _turkce_mi(kelime: str) -> bool:
        """Yabancı/bozuk kelimeleri filtrele — sadece Türkçe karakterler geçsin."""
        return bool(TURKCE_PATTERN.match(kelime.lower()))

    def _ekle(self, anahtar: str, deger: str):
        """writeback=False — nesneyi elle geri yazıyoruz."""
        mevcut = self._db.get(anahtar, [])
        mevcut.append(deger)
        self._db[anahtar] = mevcut

    # ──────────────────────────────────────────
    # Eğitim  (satır satır, RAM dostu)
    # ──────────────────────────────────────────
    def egit(self, dosya_yolu: str = VERI_DOSYASI):
        if not os.path.exists(dosya_yolu):
            print(f"[HATA] {dosya_yolu} bulunamadı!")
            sys.exit(1)

        boyut_mb = os.path.getsize(dosya_yolu) / 1_048_576
        print(f"[Eğitim başlıyor — {boyut_mb:.1f} MB, sabırlı ol kanka 😅]")

        toplam_kelime = 0
        onceki: list = []

        with open(dosya_yolu, "r", encoding="utf-8", errors="ignore") as f:
            for satir_no, satir in enumerate(f, 1):
                kelimeler = satir.lower().split()
                if not kelimeler:
                    continue

                # Satırlar arası bağlantıyı koru
                pencere = onceki + kelimeler

                for i in range(len(pencere) - 1):
                    self._ekle(self._bi_key(pencere[i]), pencere[i + 1])

                for i in range(len(pencere) - 2):
                    self._ekle(self._tri_key(pencere[i], pencere[i + 1]), pencere[i + 2])

                onceki = kelimeler[-2:] if len(kelimeler) >= 2 else kelimeler
                toplam_kelime += len(kelimeler)

                if satir_no % CHUNK_SATIR == 0:
                    print(f"  → {satir_no:,} satır / {toplam_kelime:,} kelime işlendi...")

        print(f"[Eğitim tamam ✓ — toplam {toplam_kelime:,} kelime]")
        print(f"[Hafıza '{HAFIZA_DB}.db' dosyasına yazıldı ✓]")

    # ──────────────────────────────────────────
    # Akıllı Başlangıç Noktası
    # ──────────────────────────────────────────
    def _en_iyi_baslangic(self, kelimeler: list):
        for i in range(len(kelimeler) - 1):
            k = self._tri_key(kelimeler[i], kelimeler[i + 1])
            if k in self._db:
                return (kelimeler[i], kelimeler[i + 1])

        for k in kelimeler:
            if self._bi_key(k) in self._db:
                return k

        return None

    # ──────────────────────────────────────────
    # Cevap Üretimi
    # ──────────────────────────────────────────
    def cevap_ver(self, sorgu: str, uzunluk: int = 15) -> str:
        kelimeler = sorgu.lower().split()
        if not kelimeler:
            return "Bir şeyler yaz bakalım 🙂"

        baslangic = self._en_iyi_baslangic(kelimeler)

        # ── Trigram yolu ──
        if isinstance(baslangic, tuple):
            k1, k2 = baslangic
            cumle = [k1, k2]
            for _ in range(uzunluk):
                secenekler = self._db.get(self._tri_key(k1, k2))
                if not secenekler:
                    break
                # Türkçe olmayan kelimeleri atla, max 10 denemede bulamazsan dur
                k3 = None
                for _ in range(10):
                    aday = random.choice(secenekler)
                    if self._turkce_mi(aday):
                        k3 = aday
                        break
                if not k3:
                    break
                cumle.append(k3)
                k1, k2 = k2, k3
            return " ".join(cumle).capitalize()

        # ── Bigram fallback ──
        if isinstance(baslangic, str):
            cumle = [baslangic]
            su_an = baslangic
            for _ in range(uzunluk):
                secenekler = self._db.get(self._bi_key(su_an))
                if not secenekler:
                    break
                # Türkçe olmayan kelimeleri atla, max 10 denemede bulamazsan dur
                sonraki = None
                for _ in range(10):
                    aday = random.choice(secenekler)
                    if self._turkce_mi(aday):
                        sonraki = aday
                        break
                if not sonraki:
                    break
                cumle.append(sonraki)
                su_an = sonraki
            return " ".join(cumle).capitalize()

        return "Valla kanka o konuyu hiç öğrenmedim, daha fazla veri lazım 🤷"


# ══════════════════════════════════════════════════════════════
#  ANA PROGRAM
# ══════════════════════════════════════════════════════════════
def main():
    zeka = BasitZeka()

    db_bos  = len(zeka._db) == 0
    veri_var = os.path.exists(VERI_DOSYASI)

    if db_bos and not veri_var:
        print("Kanka ne veri.txt var ne de hafiza.db — önce birini oluştur!")
        zeka.kapat()
        sys.exit(1)

    if db_bos and veri_var:
        # İlk çalıştırma — eğit
        zeka.egit(VERI_DOSYASI)
    elif not db_bos and veri_var:
        # DB zaten dolu
        print(f"[Mevcut hafıza bulundu ({HAFIZA_DB}.db) — doğrudan yükleniyor]")
        print("[Yeniden eğitmek için hafiza.db/.dir/.bak dosyalarını sil ve tekrar çalıştır]")

    print("\n╔════════════════════════════════════╗")
    print("║   Basit AI Terminaline Hoş Geldin  ║")
    print("║   Çıkmak için: exit                ║")
    print("╚════════════════════════════════════╝\n")

    try:
        while True:
            try:
                soru = input("Sen: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGörüşürüz!")
                break

            if not soru:
                continue
            if soru.lower() == "exit":
                print("Görüşürüz kanka!")
                break

            print("AI:", zeka.cevap_ver(soru))
    finally:
        zeka.kapat()


if __name__ == "__main__":
    main()
