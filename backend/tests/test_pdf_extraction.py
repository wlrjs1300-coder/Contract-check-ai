from __future__ import annotations

import os
import shutil
import stat
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api import extractions as extractions_api
from backend.app.db.models import Extraction
from backend.app.main import app
from backend.app.services import extraction_temp_files, pdf_extraction
from backend.app.services.extraction_temp_files import (
    OriginalCleanupError,
    RequestDirectory,
    cleanup_request_directory,
    create_request_directory,
)
from backend.app.services.pdf_extraction import PDFExtractionError


client = TestClient(app)


def _add_synthetic_font(writer: PdfWriter, texts: list[str]):
    characters = list(dict.fromkeys("".join(texts)))
    character_codes = {
        character: index
        for index, character in enumerate(characters, start=1)
    }
    mappings = "\n".join(
        f"<{code:04X}> <{character.encode('utf-16-be').hex().upper()}>"
        for character, code in character_codes.items()
    )
    cmap = f"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Synthetic-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
{len(character_codes)} beginbfchar
{mappings}
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end"""
    cmap_stream = DecodedStreamObject()
    cmap_stream.set_data(cmap.encode("ascii"))
    cmap_reference = writer._add_object(cmap_stream)
    descendant_font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType2"),
            NameObject("/BaseFont"): NameObject("/SyntheticFont"),
            NameObject("/CIDSystemInfo"): DictionaryObject(
                {
                    NameObject("/Registry"): NameObject("/Adobe"),
                    NameObject("/Ordering"): NameObject("/Identity"),
                    NameObject("/Supplement"): NameObject("/0"),
                }
            ),
        }
    )
    descendant_reference = writer._add_object(descendant_font)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject("/SyntheticFont"),
            NameObject("/Encoding"): NameObject("/Identity-H"),
            NameObject("/DescendantFonts"): ArrayObject(
                [descendant_reference]
            ),
            NameObject("/ToUnicode"): cmap_reference,
        }
    )
    return writer._add_object(font), character_codes


def _synthetic_text_pdf(page_texts: list[str]) -> bytes:
    writer = PdfWriter()
    font_reference, character_codes = _add_synthetic_font(writer, page_texts)

    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        encoded_text = "".join(
            f"{character_codes[character]:04X}" for character in text
        )
        content = DecodedStreamObject()
        content.set_data(
            f"BT /F1 12 Tf 50 750 Td <{encoded_text}> Tj ET".encode(
                "ascii"
            )
        )
        content_reference = writer._add_object(content)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_reference}
                )
            }
        )
        page[NameObject("/Contents")] = content_reference

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _blank_pdf(page_count: int = 1) -> bytes:
    writer = PdfWriter()

    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("synthetic-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _post_pdf(
    content: bytes,
    *,
    filename: str = "synthetic.pdf",
    content_type: str = "application/pdf",
):
    return client.post(
        "/extractions",
        files={"file": (filename, content, content_type)},
    )


def _request_directory_for_path(path: Path) -> RequestDirectory:
    metadata = os.lstat(path)
    return RequestDirectory(path, metadata.st_dev, metadata.st_ino)


def test_create_and_get_korean_text_pdf_extraction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(tmp_path / "uploads"))
    first_page = "제1조 합성 근로 조건을 확인하기 위한 문장입니다."
    second_page = "제2조 합성 계약 기간을 확인하기 위한 문장입니다."

    response = _post_pdf(_synthetic_text_pdf([first_page, second_page]))

    assert response.status_code == 201
    body = response.json()
    assert body["extraction_id"]
    assert body["filename_display"] == "synthetic.pdf"
    assert body["source_type"] == "pdf"
    assert body["page_count"] == 2
    assert body["extraction_status"] == "review_required"
    assert body["extraction_method"] == "direct"
    assert body["requires_user_review"] is True
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert first_page in body["pages"][0]["text"]
    assert second_page in body["pages"][1]["text"]
    assert body["pages"][0]["warnings"] == []
    assert body["pages"][1]["warnings"] == []

    get_response = client.get(f"/extractions/{body['extraction_id']}")

    assert get_response.status_code == 200
    assert get_response.json() == body
    assert list((tmp_path / "uploads").iterdir()) == []


def test_preserves_clause_numbers_and_page_order() -> None:
    texts = [
        "제1조 첫 번째 합성 조항의 순서를 확인합니다.",
        "제2조 두 번째 합성 조항의 순서를 확인합니다.",
    ]

    response = _post_pdf(_synthetic_text_pdf(texts))

    assert response.status_code == 201
    pages = response.json()["pages"]
    assert [page["page_number"] for page in pages] == [1, 2]
    assert "제1조" in pages[0]["text"]
    assert "제2조" in pages[1]["text"]


def test_rejects_non_pdf_extension() -> None:
    response = _post_pdf(
        _synthetic_text_pdf(["합성 텍스트 레이어 문장입니다."]),
        filename="synthetic.txt",
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_file_type"


def test_rejects_conflicting_mime_type() -> None:
    response = _post_pdf(
        _synthetic_text_pdf(["합성 텍스트 레이어 문장입니다."]),
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "file_type_mismatch"


def test_rejects_invalid_pdf_signature() -> None:
    response = _post_pdf(b"not-a-pdf")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "file_type_mismatch"


def test_rejects_encrypted_pdf() -> None:
    response = _post_pdf(_encrypted_pdf())

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "encrypted_pdf"


def test_rejects_damaged_pdf_without_internal_details() -> None:
    response = _post_pdf(b"%PDF-1.7\nsynthetic-corrupt-content")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "corrupt_document"
    assert "synthetic-corrupt-content" not in response.text
    assert "Traceback" not in response.text


def test_rejects_empty_upload() -> None:
    response = _post_pdf(b"")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "empty_document"


def test_rejects_pdf_over_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(extractions_api, "MAX_PDF_SIZE_BYTES", 100)

    response = _post_pdf(_blank_pdf())

    assert pdf_extraction.MAX_PDF_SIZE_BYTES == 20 * 1024 * 1024
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_size_limit_exceeded"


def test_rejects_pdf_over_page_limit() -> None:
    response = _post_pdf(_blank_pdf(page_count=101))

    assert pdf_extraction.MAX_PDF_PAGE_COUNT == 100
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "page_limit_exceeded"


def test_rejects_page_over_extracted_text_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdf_extraction, "MAX_PAGE_CHARACTER_COUNT", 10)

    response = _post_pdf(
        _synthetic_text_pdf(["추출 문자 제한을 확인하는 합성 문장입니다."])
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "text_limit_exceeded"


def test_rejects_pdf_when_all_pages_have_no_text() -> None:
    response = _post_pdf(_blank_pdf(page_count=2))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "extraction_empty"


def test_warns_for_partial_empty_page() -> None:
    content = _synthetic_text_pdf(
        ["합성 텍스트가 충분히 포함된 첫 번째 페이지입니다.", ""]
    )

    response = _post_pdf(content)

    assert response.status_code == 201
    body = response.json()
    assert body["warnings"] == [
        "empty_pages_detected",
        "ocr_required_pages",
    ]
    assert body["pages"][1]["warnings"] == [
        "empty_page_text",
        "ocr_required",
    ]


def test_warns_when_page_is_an_ocr_candidate() -> None:
    response = _post_pdf(_synthetic_text_pdf(["짧은 문장"]))

    assert response.status_code == 201
    body = response.json()
    assert body["warnings"] == ["ocr_required_pages"]
    assert body["pages"][0]["warnings"] == [
        "text_layer_low_quality",
        "ocr_required",
    ]


def test_parser_exception_is_safe_and_creates_no_partial_record(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    def fail_extraction(_path: Path):
        raise PDFExtractionError(
            "extraction_failed",
            "The PDF text could not be extracted.",
            status_code=500,
            retryable=True,
        )

    monkeypatch.setattr(extractions_api, "extract_text_pdf", fail_extraction)

    response = _post_pdf(_blank_pdf())

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "code": "extraction_failed",
        "message": "The PDF text could not be extracted.",
        "retryable": True,
    }
    assert db_session.scalar(select(func.count(Extraction.id))) == 0


def test_unexpected_parser_exception_is_generalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingReader:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("synthetic-sensitive-parser-detail")

    monkeypatch.setattr(pdf_extraction, "PdfReader", FailingReader)

    response = _post_pdf(b"%PDF-1.7\nsynthetic")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "extraction_failed"
    assert "synthetic-sensitive-parser-detail" not in response.text


def test_cleanup_failure_blocks_success_and_partial_record(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    real_cleanup = extractions_api.cleanup_request_directory

    def fail_after_cleanup(request_directory: RequestDirectory) -> None:
        real_cleanup(request_directory)
        raise OriginalCleanupError

    monkeypatch.setattr(
        extractions_api,
        "cleanup_request_directory",
        fail_after_cleanup,
    )

    response = _post_pdf(
        _synthetic_text_pdf(["삭제 실패를 검증하는 충분한 합성 문장입니다."])
    )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "original_cleanup_failed"
    assert db_session.scalar(select(func.count(Extraction.id))) == 0


def test_cleanup_rejects_symlink_and_preserves_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    temp_root = tmp_path / "uploads"
    target = tmp_path / "synthetic-target"
    target.mkdir()
    marker = target / "synthetic-marker.txt"
    marker.write_text("synthetic marker", encoding="utf-8")
    temp_root.mkdir()
    link = temp_root / "request-link"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))

    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Directory symlinks are unavailable: {type(exc).__name__}")

    with pytest.raises(OriginalCleanupError):
        cleanup_request_directory(_request_directory_for_path(link))

    assert marker.read_text(encoding="utf-8") == "synthetic marker"


def test_reparse_point_metadata_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    metadata = SimpleNamespace(
        st_mode=stat.S_IFDIR,
        st_file_attributes=reparse_flag,
    )
    monkeypatch.setattr(extraction_temp_files.os, "lstat", lambda _path: metadata)
    monkeypatch.setattr(Path, "is_symlink", lambda _path: False)

    assert extraction_temp_files._is_link_or_reparse(tmp_path) is True


def test_cleanup_rejects_temp_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    temp_root = tmp_path / "uploads"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))
    temp_root.mkdir()

    with pytest.raises(OriginalCleanupError):
        cleanup_request_directory(_request_directory_for_path(temp_root))

    assert temp_root.is_dir()


def test_cleanup_rejects_path_outside_temp_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    temp_root = tmp_path / "uploads"
    outside = tmp_path / "outside-request"
    outside.mkdir()
    marker = outside / "synthetic-marker.txt"
    marker.write_text("synthetic marker", encoding="utf-8")
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))

    with pytest.raises(OriginalCleanupError):
        cleanup_request_directory(_request_directory_for_path(outside))

    assert marker.exists()


def test_cleanup_rejects_replaced_request_directory_and_preserves_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    temp_root = tmp_path / "uploads"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))
    original_request = create_request_directory()
    other_request = create_request_directory()
    marker = other_request.path / "synthetic-marker.txt"
    marker.write_text("synthetic marker", encoding="utf-8")
    shutil.rmtree(original_request.path)
    os.replace(other_request.path, original_request.path)

    with pytest.raises(OriginalCleanupError):
        cleanup_request_directory(original_request)

    assert (original_request.path / marker.name).exists()
    cleanup_request_directory(
        _request_directory_for_path(original_request.path)
    )


def test_temp_root_creation_failure_is_safe_and_creates_no_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    blocked_root = tmp_path / "blocked-root"
    blocked_root.write_text("synthetic marker", encoding="utf-8")
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(blocked_root))

    response = _post_pdf(
        _synthetic_text_pdf(["임시 저장소 오류를 확인하는 합성 문장입니다."]),
        filename="private-synthetic-name.pdf",
    )

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "code": "temporary_storage_unavailable",
        "message": "Temporary document storage is unavailable.",
        "retryable": True,
    }
    assert str(blocked_root) not in response.text
    assert "private-synthetic-name.pdf" not in response.text
    assert db_session.scalar(select(func.count(Extraction.id))) == 0


def test_request_directory_creation_failure_is_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(tmp_path / "uploads"))

    def fail_mkdtemp(*_args, **_kwargs):
        raise PermissionError("synthetic-internal-path-detail")

    monkeypatch.setattr(extraction_temp_files.tempfile, "mkdtemp", fail_mkdtemp)

    response = _post_pdf(_blank_pdf(), filename="private-synthetic-name.pdf")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "temporary_storage_unavailable"
    assert response.json()["detail"]["retryable"] is True
    assert "synthetic-internal-path-detail" not in response.text
    assert "private-synthetic-name.pdf" not in response.text
    assert db_session.scalar(select(func.count(Extraction.id))) == 0


def test_server_file_path_creation_failure_is_safe_and_cleans_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    temp_root = tmp_path / "uploads"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))

    def fail_server_path(_request_directory: RequestDirectory) -> Path:
        raise OSError("synthetic-internal-server-path-detail")

    monkeypatch.setattr(
        extractions_api,
        "create_server_file_path",
        fail_server_path,
    )

    response = _post_pdf(_blank_pdf(), filename="private-synthetic-name.pdf")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "temporary_storage_unavailable"
    assert response.json()["detail"]["retryable"] is True
    assert "synthetic-internal-server-path-detail" not in response.text
    assert "private-synthetic-name.pdf" not in response.text
    assert list(temp_root.iterdir()) == []
    assert db_session.scalar(select(func.count(Extraction.id))) == 0


def test_cleanup_failure_takes_priority_over_temp_creation_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    temp_root = tmp_path / "uploads"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))
    real_create = extractions_api.create_request_directory
    real_rmtree = extraction_temp_files.shutil.rmtree
    captured: dict[str, RequestDirectory] = {}

    def capture_request() -> RequestDirectory:
        request_directory = real_create()
        captured["request"] = request_directory
        return request_directory

    def fail_server_path(_request_directory: RequestDirectory) -> Path:
        raise OSError("synthetic-internal-server-path-detail")

    def fail_rmtree(_path: Path) -> None:
        raise PermissionError("synthetic-internal-cleanup-detail")

    monkeypatch.setattr(extractions_api, "create_request_directory", capture_request)
    monkeypatch.setattr(
        extractions_api,
        "create_server_file_path",
        fail_server_path,
    )
    monkeypatch.setattr(extraction_temp_files.shutil, "rmtree", fail_rmtree)

    response = _post_pdf(_blank_pdf())

    request_directory = captured["request"]
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "original_cleanup_failed"
    assert request_directory.path.exists()
    assert "synthetic-internal-server-path-detail" not in response.text
    assert "synthetic-internal-cleanup-detail" not in response.text
    assert db_session.scalar(select(func.count(Extraction.id))) == 0

    monkeypatch.setattr(extraction_temp_files.shutil, "rmtree", real_rmtree)
    cleanup_request_directory(request_directory)


def test_target_file_open_failure_is_safe_and_cleans_request_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    content = _blank_pdf()
    temp_root = tmp_path / "uploads"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))
    real_open = Path.open

    def fail_exclusive_open(path: Path, mode: str = "r", *args, **kwargs):
        if mode == "xb":
            raise PermissionError("synthetic-internal-open-detail")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_exclusive_open)

    response = _post_pdf(content, filename="private-synthetic-name.pdf")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "temporary_storage_unavailable"
    assert "synthetic-internal-open-detail" not in response.text
    assert "private-synthetic-name.pdf" not in response.text
    assert list(temp_root.iterdir()) == []
    assert db_session.scalar(select(func.count(Extraction.id))) == 0


def test_real_rmtree_failure_leaves_marker_and_blocks_database_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    temp_root = tmp_path / "uploads"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(temp_root))
    real_create = extractions_api.create_request_directory
    real_rmtree = extraction_temp_files.shutil.rmtree
    captured: dict[str, RequestDirectory] = {}

    def create_with_marker() -> RequestDirectory:
        request_directory = real_create()
        (request_directory.path / "synthetic-marker.txt").write_text(
            "synthetic marker",
            encoding="utf-8",
        )
        captured["request"] = request_directory
        return request_directory

    def fail_rmtree(_path: Path) -> None:
        raise PermissionError("synthetic-internal-cleanup-detail")

    monkeypatch.setattr(extractions_api, "create_request_directory", create_with_marker)
    monkeypatch.setattr(extraction_temp_files.shutil, "rmtree", fail_rmtree)

    response = _post_pdf(
        _synthetic_text_pdf(["실제 삭제 실패를 확인하는 합성 문장입니다."]),
        filename="private-synthetic-name.pdf",
    )

    request_directory = captured["request"]
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "original_cleanup_failed"
    assert (request_directory.path / "synthetic-marker.txt").exists()
    assert any(request_directory.path.glob("*.pdf"))
    assert "synthetic-internal-cleanup-detail" not in response.text
    assert "private-synthetic-name.pdf" not in response.text
    assert str(request_directory.path) not in response.text
    assert db_session.scalar(select(func.count(Extraction.id))) == 0

    monkeypatch.setattr(extraction_temp_files.shutil, "rmtree", real_rmtree)
    cleanup_request_directory(request_directory)


def test_missing_extraction_returns_safe_error() -> None:
    response = client.get("/extractions/missing-extraction")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "extraction_not_found"


def test_extraction_cannot_start_analysis_before_confirmation() -> None:
    extraction_response = _post_pdf(
        _synthetic_text_pdf(["분석 차단을 확인하는 충분한 합성 문장입니다."])
    )
    extraction_id = extraction_response.json()["extraction_id"]

    response = client.post(f"/documents/{extraction_id}/analysis-jobs")

    assert extraction_response.status_code == 201
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


def test_openapi_exposes_extraction_response_schema() -> None:
    schema = client.get("/openapi.json").json()
    create_operation = schema["paths"]["/extractions"]["post"]
    get_operation = schema["paths"]["/extractions/{extraction_id}"]["get"]

    assert (
        create_operation["responses"]["201"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/ExtractionResponse"
    )
    assert (
        get_operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/ExtractionResponse"
    )
