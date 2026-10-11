cmake_minimum_required(VERSION 3.13)

project(scarab C CXX)

# Always emit build/<mode>/compile_commands.json. Consumed by:
#   - clangd / VS Code / any LSP-based editor for accurate include resolution.
#   - scarab-infra's `./sci --lint-scarab` (clang-tidy needs it to parse TUs).
#   - iwyu, clang-check, and other static analyzers.
# Cost is a single JSON file; does not affect compilation.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(SCARAB_ENABLE_LTO "Link-time optimization for the scarab executable" ON)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The modeled ISA is x86-64 even when the simulator itself runs on ARM64.
# Do not put modeled-ISA or platform definitions in global compiler flags:
# DynamoRIO separately configures its execution host and decoding target.
if(APPLE)
  set(_scarab_memtrace_default ON)
else()
  set(_scarab_memtrace_default OFF)
endif()
if(DEFINED ENV{SCARAB_ENABLE_PT_MEMTRACE})
  set(_scarab_memtrace_default ON)
endif()
option(SCARAB_ENABLE_PT_MEMTRACE "Build the processor/memory trace frontend"
       ${_scarab_memtrace_default})

set(CMAKE_C_FLAGS_SCARABOPT "-O3 -g3 -DNO_DEBUG")
set(CMAKE_CXX_FLAGS_SCARABOPT "-O3 -g3 -DNO_DEBUG")
set(CMAKE_C_FLAGS_OPT_AVX "-O3 -g3 -march=haswell -DNO_DEBUG")
set(CMAKE_CXX_FLAGS_OPT_AVX "-O3 -g3 -march=haswell -DNO_DEBUG")
if(CMAKE_BUILD_TYPE STREQUAL "OPT_AVX" AND
   NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$")
  message(FATAL_ERROR "opt-avx requires an x86-64 host; use opt on ARM64")
endif()
set(CMAKE_C_FLAGS_VALGRIND "-O0 -g3")
set(CMAKE_CXX_FLAGS_VALGRIND "-O0 -g3")
set(CMAKE_C_FLAGS_GPROF "${CMAKE_C_FLAGS_SCARABOPT} -pg")
set(CMAKE_CXX_FLAGS_GPROF "${CMAKE_CXX_FLAGS_SCARABOPT} -pg")
set(CMAKE_C_FLAGS_DEBUG "-O0 -g3 -fsanitize=address -fsanitize-address-use-after-scope")
set(CMAKE_CXX_FLAGS_DEBUG "-O0 -g3 -fsanitize=address -fsanitize-address-use-after-scope")

# Default ASan runtime options (embedded; ASAN_OPTIONS in the environment still overrides).
set(SCARAB_ASAN_DEFAULT_OPTIONS
  "check_initialization_order=true:detect_stack_use_after_return=true:strict_string_checks=true")
configure_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/support/asan_default_options.cc.in
  ${CMAKE_CURRENT_BINARY_DIR}/asan_default_options.cc
  @ONLY)

# Turn off doc generation before adding the subdirectory
set(BUILD_DOCS OFF CACHE BOOL "Disable DynamoRIO doc generation" FORCE)
#build dependencies with default warn flags, otherwise dynamorio will not build
add_subdirectory(deps)

add_compile_definitions(X86_64)
if(APPLE)
  add_compile_definitions(MACOS UNIX)
else()
  add_compile_definitions(LINUX UNIX)
endif()
if(SCARAB_ENABLE_PT_MEMTRACE)
  add_compile_definitions(ENABLE_PT_MEMTRACE)
endif()
# ARM64 can fuse multiply/add by default, while the portable x86 build cannot.
# Retain the same rounding at each operation for reproducible simulator metrics.
add_compile_options(-ffp-contract=off)

set(warn_flags -Wall -Wunused -Wno-long-long
  -Wpointer-arith
  -Werror)
set(warn_c_flags ${warn_flags}
  -Wmissing-declarations
  -Wmissing-prototypes
  -Wimplicit -Wno-unused-but-set-variable)
if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
  list(APPEND warn_c_flags -Wno-maybe-uninitialized)
endif()
set(warn_cxx_flags ${warn_flags})

add_compile_options(
  "$<$<COMPILE_LANGUAGE:C>:${warn_c_flags}>"
  "$<$<COMPILE_LANGUAGE:CXX>:${warn_cxx_flags}>"
)

add_subdirectory(ramulator)
add_subdirectory(pin/pin_lib)
if(PIN_EXEC_TESTS)
  if(APPLE)
    message(FATAL_ERROR "PIN_EXEC_TESTS requires the Intel Pin x86 Linux runtime")
  endif()
  enable_language(ASM)
endif()
add_subdirectory(pin/pin_exec/testing)

set(scarab_dirs bp debug bp/template_lib dvfs frontend globals isa libs memory power prefetcher confidence .)
if(SCARAB_ENABLE_PT_MEMTRACE)
  set(scarab_dirs ${scarab_dirs} frontend/pt_memtrace)
endif()

set(srcs)
foreach(dir IN LISTS scarab_dirs) 
    file(GLOB dir_srcs CONFIGURE_DEPENDS
      ${dir}/*.h
      ${dir}/*.cc
      ${dir}/*.c
    )
    set(srcs ${srcs} ${dir_srcs})
endforeach()

add_executable(scarab 
    ${srcs}
)

target_sources(scarab PRIVATE
  $<$<CONFIG:Debug>:${CMAKE_CURRENT_BINARY_DIR}/asan_default_options.cc>
)

find_package(Git QUIET)
add_custom_target(scarab_gitrev
  COMMAND ${CMAKE_COMMAND}
    -DGIT_EXECUTABLE=${GIT_EXECUTABLE}
    -DSCARAB_SOURCE_DIR=${CMAKE_CURRENT_SOURCE_DIR}
    -DSCARAB_GITREV_FILE=${CMAKE_CURRENT_BINARY_DIR}/gitrev
    -P ${CMAKE_CURRENT_SOURCE_DIR}/support/write_gitrev.cmake
  BYPRODUCTS ${CMAKE_CURRENT_BINARY_DIR}/gitrev
  VERBATIM)
add_dependencies(scarab scarab_gitrev)
target_include_directories(scarab PRIVATE ${CMAKE_CURRENT_BINARY_DIR} .)
find_path(SCARAB_BOOST_INCLUDE_DIR boost/multi_index_container.hpp
  HINTS /opt/homebrew/include)
if(NOT SCARAB_BOOST_INCLUDE_DIR)
  message(FATAL_ERROR "Scarab requires Boost headers (brew install boost on macOS)")
endif()
target_include_directories(scarab SYSTEM PRIVATE ${SCARAB_BOOST_INCLUDE_DIR})

target_link_libraries(scarab
    PRIVATE
        ramulator
        pin_lib_for_scarab
)
if(SCARAB_ENABLE_PT_MEMTRACE)
  target_link_libraries(scarab PRIVATE pt_memtrace)
endif()

if(SCARAB_ENABLE_LTO)
  include(CheckIPOSupported)
  check_ipo_supported(RESULT _scarab_lto_ok OUTPUT _scarab_lto_reason LANGUAGES C CXX)
  if(_scarab_lto_ok AND CMAKE_C_COMPILER_ID STREQUAL "GNU")
    include(ProcessorCount)
    ProcessorCount(_scarab_lto_jobs)
    if(_scarab_lto_jobs EQUAL 0)
      set(_scarab_lto_jobs 1)
    endif()
    # -flto=N, not the plain -flto that INTERPROCEDURAL_OPTIMIZATION emits: the
    # serial link dominates an incremental build (2m55s vs 1m15s on 20 cores).
    # GCC only -- for clang the argument names a mode, not a job count.
    target_compile_options(scarab PRIVATE -flto=${_scarab_lto_jobs} -fno-fat-lto-objects)
    target_link_options(scarab PRIVATE -flto=${_scarab_lto_jobs})
  elseif(_scarab_lto_ok)
    set_property(TARGET scarab PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
  else()
    message(STATUS "Scarab LTO not enabled: ${_scarab_lto_reason}")
  endif()
endif()
