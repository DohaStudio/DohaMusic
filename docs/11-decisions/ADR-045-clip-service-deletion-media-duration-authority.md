# ADR-045 — Clip Service 삭제 의미와 신뢰된 미디어 길이 권위

> 상태: 승인
> 작성일: 2026-08-25
> 최종 수정일: 2026-08-25
> 관련 기능: AI-native DAW D3 Clip Editing Service 선행 기반
> 관련 문서: [ADR-040](ADR-040-canonical-track-clip-working-composition-authority.md), [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Clip Domain DoD](../DoD/Clip-Domain-Persistence.md)

> 구현 추적: 2026-08-25 WorkingComposition Service가 active Clip count 기반 `TRACK_NOT_EMPTY`, exact AssetVersion·ProjectAsset·active audio Asset scope, exactly-one eligible Artifact와 persisted trusted `duration_us`를 실제 Clip create transaction에 적용했다. MP3의 `duration_us=NULL` fail-closed 정책은 유지한다.

## 1. 배경

ADR-040과 revision `20260824_0020`은 canonical Track·Clip과 integer microseconds persistence를 정의했지만, Track 삭제 시 자식 Clip 처리와 `CompositionClip.source_duration`의 신뢰 원천은 Service 구현 전에 더 좁게 확정해야 했다. 호출자가 제출한 길이나 파일 크기·평균 bitrate 추정은 불변 Payload의 정확한 길이 권위가 될 수 없다.

## 2. 결정

### 2.1 Track 삭제

- active Clip이 0개인 Track만 tombstone할 수 있다.
- active Clip이 하나라도 있으면 `TRACK_NOT_EMPTY`로 거부한다.
- V1은 Clip cascade tombstone·물리 삭제·암묵적 이동을 하지 않는다.
- active count는 같은 `working_composition_id`와 `track_id`에서 `deleted_at IS NULL`인 Clip만 센다. 다른 WorkingComposition과 이미 tombstone된 Clip은 포함하지 않는다.

### 2.2 미디어 길이 권위

- 신뢰된 ingestion/validation 경계가 immutable Payload를 읽어 길이를 계산하고 `artifacts.duration_us`에 양의 정수 microseconds로 저장한다.
- `duration_us`는 nullable additive metadata다. 기존 Artifact 행은 backfill하거나 추정하지 않고 `NULL`로 유지한다.
- Clip 생성 요청과 Provider metadata는 `source_duration` 또는 `duration_us`를 권위 값으로 공급할 수 없다. Clip Service는 Payload를 다시 probe하지 않고 저장된 trusted metadata만 사용한다.
- duration 계산은 sample/frame 수에서 `floor((samples * 1_000_000 + sample_rate / 2) / sample_rate)` 형태의 정수 half-up 반올림을 사용한다.

### 2.3 형식별 판정

| 형식 | V1 길이 권위 |
|---|---|
| WAV | RIFF/WAVE 구조를 검증하고 frame count와 sample rate로 계산한다. 선언된 frame보다 Payload가 짧으면 거부한다. |
| FLAC | 유일한 34-byte STREAMINFO의 sample rate와 total samples로 계산한다. 잘못되거나 잘린 metadata는 거부한다. |
| MP3 | 현재 의존성으로 정확한 VBR 길이를 보장할 수 없어 추정하지 않는다. 컨테이너 판별은 가능하지만 `duration_us=NULL`이며 Clip source에는 사용할 수 없다. |

### 2.4 exact AssetVersion의 Artifact 선택

Clip source 후보는 exact `AssetVersion`에 직접 귀속되고 다음을 모두 만족해야 한다.

- `artifact_kind`가 `audio` 또는 `stem`
- media type이 WAV·FLAC·MPEG allowlist
- `retention_status=active`
- 양의 trusted `duration_us`

후보가 정확히 하나일 때만 성공한다. 0개면 `SOURCE_ARTIFACT_NOT_FOUND` 또는 `SOURCE_DURATION_UNAVAILABLE`, 2개 이상이면 `SOURCE_ARTIFACT_AMBIGUOUS`로 fail-closed한다. latest Version, first Artifact, filename, path, storage locator fallback은 없다.

## 3. 구현 경계

- revision `20260824_0021`은 `artifacts.duration_us` nullable bigint와 `NULL OR > 0` CHECK만 additive하게 추가한다.
- trusted ingestion은 publish 직후 secure Artifact Resolver로 같은 Payload를 다시 열어 media type과 duration을 재검증한다.
- 오류는 Artifact ID 같은 opaque 식별자만 사용할 수 있으며 path·storage key·locator를 공개하지 않는다.
- 이 ADR 자체는 authority 결정이며, 후속 WorkingComposition Service와 Product Router가 mutation orchestration·revision/idempotency·OpenAPI 경계를 구현했다. Frontend와 실제 사용자 DB migration은 구현하지 않았다.

## 4. 대안

- Track 삭제 시 Clip cascade: 의도하지 않은 편집 손실과 Undo 의미가 불명확해 제외했다.
- Clip 요청의 duration 신뢰: 조작과 Payload drift를 막을 수 없어 제외했다.
- Clip 생성 때마다 probe: Service transaction에 파일 I/O를 넣고 권위가 중복되어 제외했다.
- MP3 file size/bitrate 추정: VBR·padding·tag 때문에 exact duration이 아니므로 제외했다.
- 여러 eligible Artifact 중 임의 선택: 재현성과 lineage를 깨므로 제외했다.

## 5. 영향과 후속 작업

기존 Artifact는 그대로 유효하지만 trusted duration이 없는 행은 Clip source로 사용할 수 없다. WorkingComposition Service는 이 authority와 active Clip count primitive를 사용해 Track 삭제와 Clip 생성을 atomic mutation으로 구현했다. 신뢰 가능한 MP3 parser dependency를 도입하려면 라이선스·정확도·운영 환경을 검증하고 이 ADR을 재검토한다.
