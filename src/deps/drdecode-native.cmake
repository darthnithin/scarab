# DynamoRIO's portable static decoder, without the instrumentation runtime.
# The pinned decoder sources model x86-64 while the C compiler targets the host.
# Keeping this separate avoids the runtime's x86 assembler selection on macOS.
function(scarab_add_native_drdecode)
  set(_dr "${CMAKE_CURRENT_SOURCE_DIR}/dynamorio")
  set(_gen "${CMAKE_CURRENT_BINARY_DIR}/dynamorio")
  file(MAKE_DIRECTORY "${_gen}/include")
  set(X86 ON)
  set(X64 ON)
  set(MACOS ON)
  set(CLANG ON)
  set(DR_HOST_X64 ON)
  if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(arm64|aarch64)$")
    set(DR_HOST_AARCH64 ON)
    set(DR_HOST_AARCHXX ON)
    set(DR_HOST_NOT_TARGET ON)
  else()
    set(DR_HOST_X86 ON)
  endif()
  set(DEBUG OFF)
  set(VERSION_NUMBER "11.90.0")
  set(VERSION_NUMBER_INTEGER 1190)
  set(OLDEST_COMPATIBLE_VERSION 1100)
  set(INSTALL_LIB_X64 "lib64")
  set(INSTALL_LIB_X86 "lib32")
  configure_file("${_dr}/make/configure.cmake.h" "${_gen}/configure.h")
  find_package(Perl REQUIRED)
  execute_process(COMMAND "${PERL_EXECUTABLE}" "${_dr}/core/gen_event_strings.pl"
    "${_dr}/core/win32/events.mc" "${_gen}/event_strings.h"
    RESULT_VARIABLE _events_result)
  if(NOT _events_result EQUAL 0)
    message(FATAL_ERROR "DynamoRIO event header generation failed: ${_events_result}")
  endif()

  # Use the same public-header exports as the upstream build. No generated ISA
  # tables are needed for its x86 decoder; all tables are pinned source files.
  set(_exports
    lib/globals_api.h:dr_defines.h
    lib/mcxtx_api.h:dr_mcxtx.h
    lib/dr_api.h:dr_api.h
    lib/dr_config.h:dr_config.h
    lib/dr_app.h:dr_app.h
    lib/dr_events.h:dr_events.h
    ir/encode_api.h:dr_ir_encode.h
    ir/decode_api.h:dr_ir_decode.h
    ir/disassemble_api.h:dr_ir_disassemble.h
    ir/opnd_api.h:dr_ir_opnd.h
    ir/instr_api.h:dr_ir_instr.h
    ir/instr_inline_api.h:dr_ir_instr_inline.h
    ir/instrlist_api.h:dr_ir_instrlist.h
    ir/dr_ir_opcodes.h:dr_ir_opcodes.h
    ir/x86/opcode_api.h:dr_ir_opcodes_x86.h
    ir/instr_create_shared_api.h:dr_ir_macros.h
    ir/x86/instr_create_api.h:dr_ir_macros_x86.h
    lib/dr_ir_utils.h:dr_ir_utils.h
    lib/dr_tools.h:dr_tools.h
    annotations_api.h:dr_annotation.h
    module_api.h:dr_modules.h
    os_api.h:dr_os_utils.h
    fragment_api.h:dr_tracedump.h
    arch/proc_api.h:dr_proc.h)
  foreach(_export IN LISTS _exports)
    string(REPLACE ":" ";" _pair "${_export}")
    list(GET _pair 0 _source)
    list(GET _pair 1 _header)
    configure_file("${_dr}/core/${_source}" "${_gen}/include/${_header}")
  endforeach()

  set(_sources
    ir/opnd_shared.c ir/x86/opnd.c ir/instr_shared.c ir/x86/instr.c
    ir/instrlist.c ir/decode_shared.c ir/x86/decode.c ir/encode_shared.c
    ir/x86/encode.c ir/isa_regdeps/encoding_common.c ir/isa_regdeps/encode.c
    ir/isa_regdeps/decode.c ir/isa_regdeps/disassemble.c
    ir/disassemble_shared.c ir/x86/disassemble.c ir/ir_utils_shared.c
    ir/x86/ir_utils.c ir/x86/decode_table.c ir/x86/decode_fast.c
    ir/decodelib.c string.c io.c
    drlibc/drlibc.c drlibc/drlibc_notdr_error.c
    drlibc/drlibc_notdr_ignoreassert.c drlibc/drlibc_notdr_saferead.c
    drlibc/drlibc_notdr_stats.c)
  list(TRANSFORM _sources PREPEND "${_dr}/core/")
  add_library(drdecode STATIC ${_sources}
    "${CMAKE_CURRENT_SOURCE_DIR}/drdecode-native-support.c")
  target_compile_definitions(drdecode PRIVATE
    DYNAMORIO_INTERNAL NOT_DYNAMORIO_CORE_PROPER STANDALONE_DECODER)
  if(DR_HOST_AARCH64)
    # os_public.h keys its signal-context typedef from the decoded ISA.
    # A decoder never handles signals; use the actual host's context type.
    target_compile_definitions(drdecode PRIVATE _STRUCT_MCONTEXT_AVX64=_STRUCT_MCONTEXT64)
  endif()
  target_compile_options(drdecode PRIVATE -O2 -g0 -Wno-error)
  target_include_directories(drdecode PRIVATE
    "${_gen}" "${_dr}/core/lib" "${_dr}/core/arch" "${_dr}/core/ir"
    "${_dr}/core/unix" "${_dr}/core/arch/x86" "${_dr}/core/ir/x86"
    "${_dr}/core/drlibc")
  target_include_directories(drdecode SYSTEM PUBLIC "${_gen}/include")
  configure_file("${_dr}/libutil/dr_frontend.h" "${_gen}/include/dr_frontend.h" COPYONLY)
  add_library(drfrontendlib STATIC "${CMAKE_CURRENT_SOURCE_DIR}/drfrontend-native.c")
  target_include_directories(drfrontendlib SYSTEM PUBLIC "${_gen}/include")
endfunction()
scarab_add_native_drdecode()
