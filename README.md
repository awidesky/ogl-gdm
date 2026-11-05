# ogl-gdm

This fork updates the original [OpenGL-Tutorial](http://www.opengl-tutorial.org)'s outdated dependencies using [GDM](https://github.com/awidesky/gdm).

The previous fork, [ogl-macfix](https://github.com/awidesky/ogl-macFix), was a simple patch that used newer OpenGL dependencies only on macOS and assumed they were installed via `brew`.  
`ogl-gdm` uses [GDM](https://github.com/awidesky/gdm) to install dependencies, so it uses up-to-date OpenGL dependencies on all platforms and builds with recent CMake.  
It also uses the [GLUtil](https://github.com/awidesky/gdm#glutil---opengl-utility-library) library to show extra debug information when an OpenGL error occurs.

Note that Assimp, Bullet, and AntTweakBar are still bundled, since they're not supported by `GDM`.
AntTweakBar is no longer maintained and causes build problems on macOS (on Windows it builds successfully but does not work correctly at runtime). The samples that depend on it are `tutorial17_rotations`, `misc05_picking_slow_easy`, `misc05_picking_custom`, and `misc05_picking_BulletPhysics`, and those targets are excluded from ALL_BUILD on macOS.
  
  
컴퓨터그래픽스 수업 실습을 위해 오신 경우, 혹시라도 설치나 빌드, 사용 중 문제가 생기면 issue에 남겨 주세요.
환경과 오류 메시지를 알려 주시면 최대한 도움 드리겠습니다.