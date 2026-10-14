"""Preserve declared direction and actual selected generation arguments separately."""

if not __debug__:
    raise RuntimeError('Evidence tools require normal Python; optimization disables critical checks')
import argparse
from pathlib import Path
import hashlib
import json

def unwrap(value):
    if isinstance(value, str) and Path(value).is_file():
        value = json.loads(Path(value).read_text())
    if isinstance(value, dict) and isinstance(value.get('args'), dict):
        value = value['args']
    return value if isinstance(value, dict) and isinstance(value.get('prompt'), str) else None

def actual_args(record):
    prov = record.get('tool_provenance', {})
    if isinstance(prov, dict) and ('orphan' in str(prov.get('provenance_method', '')) or prov.get('outputreceipt_available') is False):
        return None
    if 'actual_tool_arguments' in record:
        return unwrap(record['actual_tool_arguments'])
    for key in ['actual_selected_args', 'actual_tool_args', 'actual_arguments']:
        if key in record:
            result = unwrap(record[key])
            if result:
                return result
    if isinstance(prov, dict):
        for key in ['actual_arguments_path', 'args', 'request_path', 'arguments']:
            if prov.get(key):
                result = unwrap(prov[key])
                if result:
                    return result
    for key in ['actual_request_path', 'request_path']:
        if record.get(key):
            result = unwrap(record[key])
            if result:
                return result
    return None


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Selected-provenance output exists; preserve and inspect it')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    source = args.review.resolve()
    records = {r['id']: r for r in json.loads(source.read_text())['records']}
    original = args.plan.resolve()
    plan = json.loads(original.read_text())
    confirmed = 0
    unknown = []
    for scene in plan['scenes']:
        row = records.get(scene['id'])
        if not row:
            scene['selected_source_state'] = 'pending_actual_review'
            continue
        generation_args = actual_args(row)
        assert row.get('state') == 'pass' and row.get('reviewer') and row.get('notes')
        assert hashlib.sha256(Path(row['image']).read_bytes()).hexdigest() == row['image_sha256']
        confirmed += generation_args is not None
        if generation_args is None:
            unknown.append(scene['id'])
        scene.update(selected_source_state='pass', selected_image=row['image'],
                     selected_image_sha256=row['image_sha256'],
                     original_declared_prompt=scene['prompt'],
                     original_declared_references=scene['references'],
                     selected_generation_arguments=generation_args,
                     actual_generation_argument_association='confirmed_saved_receipt' if generation_args else 'unconfirmed_orphan_or_unresolved_receipt',
                     selected_generation_review_record=row)
    plan['original_source_plan'] = str(original)
    plan['actual_selected_source_review'] = str(source)
    plan['actual_selected_source_review_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    plan['import_annotation_policy'] = 'Native location/registry metadata and post-generation documentation may be appended in an import copy. Original declared direction and actual selected generation arguments/reference order are preserved separately; no post-generation annotation is claimed sent to the image provider.'
    out = args.output.resolve()
    out.write_text(json.dumps(plan, indent=2) + '\n')
    print(args.output, 'selected', len(records), 'actual confirmed args', confirmed, 'unknown', unknown,
          'path', out, 'SHA', hashlib.sha256(out.read_bytes()).hexdigest())
