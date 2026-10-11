# Initialize only missing dependencies: an already initialized checkout must
# remain configurable offline and without modifying .git/config.
if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/xed/mfile.py" OR
   NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/mbuild/mbuild/__init__.py" OR
   (SCARAB_ENABLE_PT_MEMTRACE AND NOT EXISTS
     "${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/CMakeLists.txt"))
  find_package(Git REQUIRED)
  execute_process(COMMAND ${GIT_EXECUTABLE} submodule update --init --recursive
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}/..
    RESULT_VARIABLE _scarab_submodule_status)
  if(NOT _scarab_submodule_status EQUAL 0)
    message(FATAL_ERROR "Unable to initialize pinned dependencies; run git submodule update --init --recursive")
  endif()
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(SCARAB_XED_JOBS 4 CACHE STRING "Parallel jobs for the Intel XED build")
set(_xed_build_dir "${CMAKE_CURRENT_BINARY_DIR}/xed")
file(MAKE_DIRECTORY "${_xed_build_dir}")
file(GLOB_RECURSE _xed_inputs CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/xed/src/*"
  "${CMAKE_CURRENT_SOURCE_DIR}/xed/include/*"
  "${CMAKE_CURRENT_SOURCE_DIR}/xed/pysrc/*"
  "${CMAKE_CURRENT_SOURCE_DIR}/xed/datafiles/*"
  "${CMAKE_CURRENT_SOURCE_DIR}/mbuild/mbuild/*.py")
if(CMAKE_C_COMPILER_ID MATCHES "Clang")
  set(_xed_compiler clang)
else()
  set(_xed_compiler gnu)
endif()
set(_xed_environment)
if(APPLE)
  execute_process(COMMAND xcrun --show-sdk-path
    OUTPUT_VARIABLE _xed_sdk OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE _xed_sdk_result)
  if(NOT _xed_sdk_result EQUAL 0)
    message(FATAL_ERROR "Unable to locate the macOS SDK; install Xcode Command Line Tools")
  endif()
  list(APPEND _xed_environment "SDKROOT=${_xed_sdk}")
endif()
add_custom_command(OUTPUT "${_xed_build_dir}/libxed.a"
  COMMAND ${CMAKE_COMMAND} -E env ${_xed_environment} ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/xed/mfile.py
    --build-dir=${_xed_build_dir} --compiler=${_xed_compiler}
    --cc=${CMAKE_C_COMPILER} --cxx=${CMAKE_CXX_COMPILER}
    --jobs=${SCARAB_XED_JOBS}
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/xed
  DEPENDS ${_xed_inputs} xed/mfile.py xed/xed_mbuild.py xed/xed_build_common.py
  COMMENT "Building Intel XED for the native execution host"
  VERBATIM)
add_custom_target(scarab_xed_build DEPENDS "${_xed_build_dir}/libxed.a")
add_library(xed INTERFACE)
add_dependencies(xed scarab_xed_build)
target_include_directories(xed INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}/xed/include/public/xed/ ${_xed_build_dir})
target_link_libraries(xed INTERFACE "${_xed_build_dir}/libxed.a")

if(SCARAB_ENABLE_PT_MEMTRACE)
  if(APPLE)
    include(${CMAKE_CURRENT_SOURCE_DIR}/memtrace-native.cmake)
  else()
    # Upstream DynamoRIO links these by target name; imported targets also carry
    # headers and library paths when dependencies live in a user prefix.
    foreach(_codec snappy lz4)
      find_path(SCARAB_${_codec}_INCLUDE_DIR ${_codec}.h)
      find_library(SCARAB_${_codec}_LIBRARY ${_codec})
      if(NOT SCARAB_${_codec}_INCLUDE_DIR OR NOT SCARAB_${_codec}_LIBRARY)
        message(FATAL_ERROR "Memtrace requires ${_codec} headers and library")
      endif()
      if(NOT TARGET ${_codec})
        add_library(${_codec} UNKNOWN IMPORTED)
        set_target_properties(${_codec} PROPERTIES
          IMPORTED_LOCATION "${SCARAB_${_codec}_LIBRARY}"
          INTERFACE_INCLUDE_DIRECTORIES "${SCARAB_${_codec}_INCLUDE_DIR}")
      endif()
    endforeach()
    add_subdirectory(dynamorio)
    add_library(pt_memtrace INTERFACE)

    target_include_directories(pt_memtrace SYSTEM
      INTERFACE
      ${CMAKE_BINARY_DIR}/deps/dynamorio/include/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/ext/drcovlib/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/ext/drmgr/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/ext/drcontainers/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/core/lib/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/clients/drcachesim/reader/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/clients/drcachesim/common/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/clients/drcachesim/tracer/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/clients/drcachesim/scheduler/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/clients/drcachesim/
      ${CMAKE_CURRENT_SOURCE_DIR}/dynamorio/third_party/zlib/contrib/
      )

    target_link_libraries(pt_memtrace
      INTERFACE
      dynamorio
      drmemtrace_raw2trace
      directory_iterator
      drfrontendlib
      drutil_static
      drmgr_static
      drmemfuncs

      drlibc
      drcovlib_static
      drx_static
      drreg_static
      drcontainers
      drmemtrace_analyzer
      minizip
      xed
      snappy
      dl
      z
      rt
      pthread
      )
  endif()
endif()
