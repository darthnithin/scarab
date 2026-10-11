# Keep the version stamp available for direct CMake builds as well as make opt.
set(_revision unknown)
if(GIT_EXECUTABLE AND EXISTS "${GIT_EXECUTABLE}")
  execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse --short HEAD
    WORKING_DIRECTORY "${SCARAB_SOURCE_DIR}/.."
    OUTPUT_VARIABLE _git_revision OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET RESULT_VARIABLE _result)
  if(_result EQUAL 0)
    set(_revision "${_git_revision}")
  endif()
endif()
set(_contents "\"${_revision}\"\n")
if(EXISTS "${SCARAB_GITREV_FILE}")
  file(READ "${SCARAB_GITREV_FILE}" _previous)
endif()
if(NOT _contents STREQUAL _previous)
  file(WRITE "${SCARAB_GITREV_FILE}" "${_contents}")
endif()
