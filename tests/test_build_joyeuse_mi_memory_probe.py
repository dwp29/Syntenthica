import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "synthetica-project/build_joyeuse_mi_memory_probe.py"
SPEC = importlib.util.spec_from_file_location("joyeuse_mi_memory_probe", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class TestMiMemoryProbe(unittest.TestCase):
    def test_git_blob_id_and_anchor_checks(self):
        self.assertEqual(mod.git_blob_id(b"hello"), "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0")
        self.assertEqual(mod.replace_exact("abca", "a", "x", 2), "xbcx")
        with self.assertRaisesRegex(ValueError, "exact anchor"):
            mod.replace_exact("abca", "a", "x")

    def test_apply_is_fail_closed_and_keeps_ufs_symbols_unexported(self):
        donor = {
            "Kconfig": 'config MI_MEMORY_SYSFS\n\ttristate "show memory info"\n\tdepends on MIHW\n',
            "Makefile": "obj-$(CONFIG_MI_MEMORY_SYSFS) += mi_memory.o\n",
            "mi_memory_sysfs.c": "\tmi_memory = kzalloc(sizeof(struct memory_info), GFP_KERNEL);\n",
            "mi_ufs_info.c": "\tsend_ufs_hba_data(&hba, &sdev);\n" * 10,
            "mem_interface.c": (
                "int ufshcd_read_desc_mi(struct ufs_hba *hba, enum desc_idn desc_id,\n"
                "\t\tint desc_index, void *buf, u32 size)\n{\n\tint ret = 0;\n}\n"
                "\tu8 *desc_buf;\n\tu8 desc_buf[8] = {0};\n\tint ret;\n"
            ),
        }
        base = {
            "drivers/misc/Kconfig": "endmenu\n",
            "drivers/misc/Makefile": "# base\n",
            "drivers/scsi/ufs/ufshcd.c": (
                "static int ufshcd_read_desc_param(void) {}\n"
                "static int ufshcd_read_string_desc(void) {}\n"
                "static int ufshcd_slave_configure(struct scsi_device *sdev)\n{\n"
                "\tufshcd_crypto_setup_rq_keyslot_manager(hba, q);\n}\n"
            ),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree, donors = root / "tree", root / "donor"
            donors.mkdir()
            for path, content in donor.items():
                (donors / path).write_text(content)
            for path, content in base.items():
                p = tree / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
            donor_ids = {k: mod.git_blob_id(v.encode()) for k, v in donor.items()}
            base_ids = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in base.items()}
            with patch.object(mod, "DONOR_BLOBS", donor_ids), patch.object(mod, "BASE_SHA256", base_ids):
                (donors / "Makefile").write_text("tampered")
                with self.assertRaisesRegex(ValueError, "blob mismatch"):
                    mod.apply_probe(tree, donors)
                self.assertFalse((tree / "drivers/misc/mi-memory").exists())
                (donors / "Makefile").write_text(donor["Makefile"])
                mod.apply_probe(tree, donors)
                out = tree / "drivers/misc/mi-memory"
                kconfig = (out / "Kconfig").read_text()
                self.assertIn('bool "Experimental', kconfig)
                self.assertIn("SCSI_UFS_QCOM", kconfig)
                self.assertEqual((out / "mi_ufs_info.c").read_text().count("if (!hba || !sdev)"), 10)
                self.assertIn("if (!mi_memory)", (out / "mi_memory_sysfs.c").read_text())
                ufs = (tree / "drivers/scsi/ufs/ufshcd.c").read_text()
                self.assertIn("sdev->lun == 2", ufs)
                self.assertNotIn("EXPORT_SYMBOL(ufshcd_read_desc_param)", ufs)
                self.assertNotIn("EXPORT_SYMBOL(ufshcd_read_string_desc)", ufs)
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    mod.apply_probe(tree, donors)


if __name__ == "__main__":
    unittest.main()
