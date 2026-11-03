#!/usr/bin/env python3
"""Prepare a source-only AxSandbox vault quarantine, NOT a functional vault.

This prototype disables import, restore, delete and legacy migration, and
stops automatic deletion of metadata for missing vault files. It is not built,
signed, installed or included in a ROM. It is intentionally incompatible with
normal vault workflows until a proper transactional design and device tests
exist. Other cache/media-bridge, authentication, crypto and sandbox code remain
outside the scope of this narrow quarantine.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

SOURCE_COMMIT='df0f91f826a32bb5e7cd2aff53de80f6b1b99f62'
SOURCE_BLOB='0c21171f69467de80da609d5951312559b91b366'
SOURCE_SHA256='1883370ab8b947990c65f06b6d317990d068dc521e629e9e452ec89931d43ab5'
MAX_SOURCE=512*1024

class QuarantineError(RuntimeError):pass

REPLACEMENTS={
'    fun migrateLegacyIfNeeded() {':'''    fun migrateLegacyIfNeeded() {
        if (metadataFile.exists()) {
            Log.w(TAG, "Legacy vault migration is disabled in quarantine")
        }
    }''',
'    fun importFile(uri: Uri): Boolean {':'''    @Suppress("UNUSED_PARAMETER")
    fun importFile(uri: Uri): Boolean {
        Log.w(TAG, "Vault import is disabled in quarantine")
        return false
    }''',
'    private fun cleanupOriginal(uri: Uri, path: String?) {':'',
'    fun restoreFile(vaultFile: VaultFile): Boolean {':'''    @Suppress("UNUSED_PARAMETER")
    fun restoreFile(vaultFile: VaultFile): Boolean {
        Log.w(TAG, "Vault restore is disabled in quarantine")
        return false
    }''',
'    fun deleteFiles(vaultFiles: List<VaultFile>) {':'''    fun deleteFiles(vaultFiles: List<VaultFile>) {
        if (vaultFiles.isNotEmpty()) {
            Log.w(TAG, "Vault deletion is disabled in quarantine")
        }
    }''',
'    fun deleteFile(vaultFile: VaultFile): Boolean {':'''    @Suppress("UNUSED_PARAMETER")
    fun deleteFile(vaultFile: VaultFile): Boolean {
        Log.w(TAG, "Vault deletion is disabled in quarantine")
        return false
    }''',
'    fun getVaultFiles(): List<VaultFile> {':'''    fun getVaultFiles(): List<VaultFile> {
        val dbFiles = dbHelper.getAllFiles()
        val binFiles = vaultDir.listFiles { f -> f.extension == "bin" }?.associateBy { it.nameWithoutExtension } ?: emptyMap()
        return dbFiles.mapNotNull { entry ->
            val binFile = binFiles[entry.id]
            if (binFile != null) attachFile(entry, binFile) else null
        }
    }''',
}


def _method_end(text: str,brace: int) -> int:
    """Find a Kotlin body's closing brace, excluding strings/comments/chars."""
    if brace>=len(text) or text[brace]!='{':raise QuarantineError('Missing method body')
    i=brace;depth=0;mode='code';block_depth=0
    while i<len(text):
        c=text[i];n=text[i:i+2];three=text[i:i+3]
        if mode=='code':
            if n=='//':mode='line';i+=2;continue
            if n=='/*':mode='block';block_depth=1;i+=2;continue
            if three=='"""':mode='triple';i+=3;continue
            if c=='"':mode='string';i+=1;continue
            if c=="'":mode='char';i+=1;continue
            if c=='{':depth+=1
            elif c=='}':
                depth-=1
                if depth==0:return i+1
                if depth<0:raise QuarantineError('Unexpected closing brace')
        elif mode=='line':
            if c=='\n':mode='code'
        elif mode=='block':
            if n=='/*':block_depth+=1;i+=2;continue
            if n=='*/':
                block_depth-=1;i+=2
                if block_depth==0:mode='code'
                continue
        elif mode=='triple':
            if three=='"""':mode='code';i+=3;continue
        elif mode in ('string','char'):
            if c=='\\':i+=2;continue
            if (mode=='string' and c=='"') or (mode=='char' and c=="'"):mode='code'
        i+=1
    raise QuarantineError('Unclosed Kotlin method, comment or string')


def prepare(data: bytes,*,expected_sha256: str=SOURCE_SHA256) -> tuple[bytes,dict]:
    if not 0<len(data)<=MAX_SOURCE or hashlib.sha256(data).hexdigest()!=expected_sha256:
        raise QuarantineError('Source does not match the pinned AxSandbox file')
    try:text=data.decode('utf-8')
    except UnicodeDecodeError as exc:raise QuarantineError('Source is not UTF-8') from exc
    edits=[]
    for signature,replacement in REPLACEMENTS.items():
        if text.count(signature)!=1:raise QuarantineError('Missing or ambiguous method: '+signature.strip())
        start=text.index(signature)
        if start and text[start-1]!='\n':raise QuarantineError('Method signature is not at the start of a line')
        end=_method_end(text,start+len(signature)-1);edits.append((start,end,replacement,signature))
    edits.sort()
    if any(a[1]>b[0] for a,b in zip(edits,edits[1:])):raise QuarantineError('Method ranges overlap')
    out=[];pos=0
    for start,end,replacement,_ in edits:
        out.append(text[pos:start]);out.append(replacement);pos=end
    out.append(text[pos:]);changed=''.join(out)
    # Guard against accidentally retaining one of the known destructive paths.
    for forbidden in ('cleanupOriginal(', 'metadataFile.delete()', 'targetFile.delete()',
                      'dbHelper.deleteFile(vaultFile.id)', 'dbHelper.deleteFile(entry.id)',
                      'FileOutputStream(destFile)', 'FileOutputStream(targetFile)'):
        if forbidden in changed:raise QuarantineError('Known destructive path remains: '+forbidden)
    output=changed.encode('utf-8')
    return output,{'status':'SOURCE_QUARANTINE_ONLY_NOT_BUILT_NOT_INSTALLED_HOLD',
        'source_commit':SOURCE_COMMIT,'source_blob':SOURCE_BLOB,'source_sha256':expected_sha256,
        'output_sha256':hashlib.sha256(output).hexdigest(),'replaced_method_count':len(edits),
        'disabled':['legacy_migration','vault_import','vault_restore','vault_delete','automatic_missing_file_metadata_deletion'],
        'vault_is_functional':False,'other_source_bytes_unchanged':True,
        'limitations':['This intentionally disables core vault features and is not a completed fix or a ROM build.',
                       'Cache/media-bridge cleanup, other providers, authentication, cryptography and concurrency are not audited here.',
                       'No source-to-binary build, Android compile, platform signing, data-safety or device test has occurred.',
                       'AxSandbox framework, system UID, permission, compatibility and licensing blockers remain.']}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    created=False
    try:
        if (a.source.is_symlink() or not a.source.is_file() or a.source.stat().st_size>MAX_SOURCE
            or a.output.exists() or a.output.is_symlink()):
            raise QuarantineError('Use a bounded ordinary source and a new output path')
        data=a.source.read_bytes();output,report=prepare(data)
        with a.output.open('xb') as out:
            created=True;out.write(output);out.flush();os.fsync(out.fileno())
        if a.source.read_bytes()!=data:raise QuarantineError('Source changed during preparation')
        print(json.dumps(report,indent=2));return 0
    except (QuarantineError,OSError) as exc:
        if created:
            try:a.output.unlink(missing_ok=True)
            except OSError:pass
        print('Vault quarantine not prepared: '+str(exc),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
