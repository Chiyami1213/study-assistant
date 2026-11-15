"""Windows version information for the exes (build_exe.py, build_installer.py): the file's properties dialog and what antivirus programs read.
An exe without a name, a version and a publisher is treated with more suspicion than one that says what it is."""
from version import VERSION

REPO_URL = "https://github.com/Chiyami1213/study-assistant"


def write_version_file(path, description, original_name):
    nums = (list(int(x) for x in VERSION.split(".")) + [0, 0, 0, 0])[:4]
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tuple(nums)}, prodvers={tuple(nums)}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Study Assistant (open source)'),
      StringStruct('FileDescription', '{description}'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', '{original_name}'),
      StringStruct('LegalCopyright', 'Open source: {REPO_URL}'),
      StringStruct('OriginalFilename', '{original_name}.exe'),
      StringStruct('ProductName', 'Study Assistant'),
      StringStruct('ProductVersion', '{VERSION}'),
      StringStruct('Comments', 'Source code and checksums: {REPO_URL}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
