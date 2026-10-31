"""Static R0 module signature/CRC checks; no kernel/module/APK/daemon execution."""
import hashlib
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

def sections(elf):
    if elf[:6] != b'\x7fELF\x02\x01':
        raise ValueError('requires little-endian ELF64')
    off = struct.unpack_from('<Q', elf, 40)[0]
    size, count, string_index = struct.unpack_from('<HHH', elf, 58)
    if size != 64 or off+size*count > len(elf) or string_index >= count:
        raise ValueError('ELF section bounds')
    headers = [struct.unpack_from('<IIQQQQIIQQ', elf, off+i*64) for i in range(count)]
    st = headers[string_index]; strings = elf[st[4]:st[4]+st[5]]
    result = {}
    for h in headers:
        name = strings[h[0]:].split(b'\0',1)[0].decode()
        if h[1] != 8:  # SHT_NOBITS is not file-backed.
            if h[4]+h[5] > len(elf): raise ValueError('section outside file')
            result[name] = elf[h[4]:h[4]+h[5]]
    return result

def verify(z):
    cert = z.read('reference/local-build-public-signing-cert.x509')
    raw = zlib.decompress(z.read('experimental/kernel/Image.gz'),31)
    if cert not in raw: raise ValueError('signing certificate absent from raw R0 kernel')
    symvers = {line.split()[1]: int(line.split()[0],16)
               for line in z.read('records/Module.symvers').decode().splitlines() if line.strip()}
    report = {'scope': 'R0 own modules only; NOT inventory/ABI/trust proof for installed vendor modules',
              'public_cert_sha256': hashlib.sha256(cert).hexdigest(),
              'public_cert_bytes_present_in_r0_kernel': True, 'modules': []}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/'cert.der').write_bytes(cert)
        subprocess.run(['openssl','x509','-inform','DER','-in',str(root/'cert.der'),'-out',str(root/'cert.pem')],check=True,capture_output=True)
        for name in z.namelist():
            if not name.endswith('.ko'): continue
            module = z.read(name)
            marker = b'~Module signature appended~\n'
            if not module.endswith(marker): raise ValueError('signature marker')
            header = module[-len(marker)-12:-len(marker)]
            if header[2] != 2 or header[3] or header[4]: raise ValueError('unsupported PKCS7 signature header')
            siglen = struct.unpack_from('>I',header,8)[0]
            signature_start = len(module)-len(marker)-12-siglen
            if signature_start <= 0: raise ValueError('signature length')
            unsigned, signature = module[:signature_start], module[signature_start:-len(marker)-12]
            (root/'module.bin').write_bytes(unsigned); (root/'signature.der').write_bytes(signature)
            # -nointern pins the supplied signer certificate. -noverify skips
            # CA-chain validation, NOT cryptographic signature verification.
            # Kernel trust is separately evidenced by exact embedded cert bytes.
            proc = subprocess.run(['openssl','cms','-verify','-binary','-inform','DER',
                '-in',str(root/'signature.der'),'-content',str(root/'module.bin'),
                '-certfile',str(root/'cert.pem'),'-nointern','-noverify','-out',str(root/'verified.bin')],
                capture_output=True)
            if proc.returncode or (root/'verified.bin').read_bytes() != unsigned:
                raise ValueError('module signature verification failed: '+name)
            sec = sections(unsigned); versions = sec.get('__versions',b'')
            if not versions or len(versions)%64: raise ValueError('__versions layout')
            imports = {}
            for i in range(0,len(versions),64):
                crc = struct.unpack_from('<Q',versions,i)[0]
                symbol = versions[i+8:i+64].split(b'\0',1)[0].decode()
                if symbol not in symvers or symvers[symbol] != crc:
                    raise ValueError('R0 import CRC mismatch: '+symbol)
                imports[symbol] = f'{crc:08x}'
            fields = [v.decode() for v in sec['.modinfo'].split(b'\0') if b'=' in v]
            info = dict(v.split('=',1) for v in fields)
            report['modules'].append({'path': name, 'sha256': hashlib.sha256(module).hexdigest(),
                'name': info.get('name'), 'vermagic': info.get('vermagic'), 'depends': info.get('depends'),
                'pkcs7_signature_verified_with_pinned_public_cert': True,
                'import_crc_count': len(imports), 'all_import_crcs_equal_r0_Module_symvers': True,
                'module_layout_crc': imports.get('module_layout')})
    if len(report['modules']) != 3: raise ValueError('expected three R0 modules')
    return report
