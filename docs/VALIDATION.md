# Local release validation

Validated on 2026-11-21 with Python 3.11 on macOS.

- 25 automated tests passed in the development environment.
- The source distribution and universal Python wheel built successfully using
  an isolated build environment.
- A fresh virtual environment (without system site packages) installed the wheel
  and the pinned numerical dependencies. The same 25 tests passed against the
  installed package, run from outside the source repository.
- `pip check` reported no broken requirements in that fresh environment.
- A synthetic 360-s lab run produced one computed record. A synthetic MRI run
  produced nine 60-s windows with 30-s steps, without recording-level errors.
- The source release scanner regenerated the included 60-s example and compared
  its bytes with the packaged fixture. Only explicitly generated data is shipped.
- GitHub Actions is configured but has not been run on a remote repository.

Exact runtime/test versions are in `requirements-py311-tested.lock`. This is
software validation on synthetic data. It establishes neither MRI artifact
rejection accuracy nor clinical/physiological validity. No real participant data
was used or copied into this release's tests or examples.
