# Build only DynamoRIO's standalone x86 decoder on the native host. Tracing and
# injection require platform-specific runtime machinery that replay does not use.
include(${CMAKE_CURRENT_SOURCE_DIR}/drdecode-native.cmake)

find_package(ZLIB REQUIRED)
find_path(SCARAB_SNAPPY_INCLUDE_DIR snappy.h HINTS /opt/homebrew/include)
find_library(SCARAB_SNAPPY_LIBRARY snappy HINTS /opt/homebrew/lib)
find_path(SCARAB_LZ4_INCLUDE_DIR lz4.h HINTS /opt/homebrew/include)
find_library(SCARAB_LZ4_LIBRARY lz4 HINTS /opt/homebrew/lib)
if(NOT SCARAB_SNAPPY_INCLUDE_DIR OR NOT SCARAB_SNAPPY_LIBRARY OR
   NOT SCARAB_LZ4_INCLUDE_DIR OR NOT SCARAB_LZ4_LIBRARY)
  message(FATAL_ERROR "Native memtrace requires snappy and lz4 (brew install snappy lz4)")
endif()
set(_dr_source "${CMAKE_CURRENT_SOURCE_DIR}/dynamorio")
set(_dr_cache "${_dr_source}/clients/drcachesim")
add_library(scarab_minizip STATIC
  ${_dr_source}/third_party/zlib/contrib/minizip/unzip.c
  ${_dr_source}/third_party/zlib/contrib/minizip/ioapi.c)
target_link_libraries(scarab_minizip PUBLIC ZLIB::ZLIB)
target_include_directories(scarab_minizip PUBLIC ${_dr_source}/third_party/zlib/contrib)
add_library(pt_memtrace STATIC
  ${_dr_cache}/reader/reader.cpp
  ${_dr_cache}/reader/file_reader.cpp
  ${_dr_cache}/reader/compressed_file_reader.cpp
  ${_dr_cache}/reader/snappy_file_reader.cpp
  ${_dr_cache}/reader/zipfile_file_reader.cpp
  ${_dr_cache}/common/trace_entry.cpp
  ${_dr_cache}/common/snappy_consts.cpp
  ${_dr_cache}/common/crc32c.cpp
  ${_dr_cache}/common/directory_iterator.cpp)
target_compile_definitions(pt_memtrace PUBLIC
  SCARAB_STANDALONE_DECODER UNIX MACOS X86_64 HAS_ZLIB HAS_ZIP HAS_SNAPPY HAS_LZ4)
target_include_directories(pt_memtrace SYSTEM PUBLIC
  ${CMAKE_CURRENT_BINARY_DIR}/dynamorio/include
  ${_dr_cache}/reader ${_dr_cache}/common
  ${SCARAB_SNAPPY_INCLUDE_DIR} ${SCARAB_LZ4_INCLUDE_DIR})
target_link_libraries(pt_memtrace PUBLIC drdecode drfrontendlib scarab_minizip
  ${SCARAB_SNAPPY_LIBRARY} ${SCARAB_LZ4_LIBRARY} ZLIB::ZLIB xed)
