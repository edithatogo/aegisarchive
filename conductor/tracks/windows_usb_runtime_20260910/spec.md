# Windows USB runtime deployment

The Windows launcher found no portable Python on the USB. Previous CI used runner-installed Python and generated a fixed receipt instead of exercising capture.

- AC1: Prepare a checksum-pinned official Windows x64 embedded runtime within the application folder, without target-machine installation or launch-time downloads.
- AC2: Test the real CMD launcher and synthetic capture using that runtime with system Python absent from PATH.
- AC3: Keep runtime binaries outside Git, document preparation, and distinguish hosted validation from restricted-workstation acceptance.
