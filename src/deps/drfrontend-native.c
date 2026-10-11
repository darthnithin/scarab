/* The filesystem helpers used by DynamoRIO's trace directory iterator.
 * Its full frontend library also loads/injects programs, which is unrelated
 * to replay and uses operating-system runtime assembly. */
#include <stdbool.h>
#include <errno.h>
#include <sys/stat.h>
#include "dr_frontend.h"

drfront_status_t drfront_dir_exists(const char* path, bool* is_dir) {
  struct stat st;
  if (is_dir == NULL)
    return DRFRONT_ERROR_INVALID_PARAMETER;
  if (path == NULL || stat(path, &st) != 0) {
    *is_dir = false;
    return DRFRONT_ERROR_INVALID_PATH;
  }
  *is_dir = S_ISDIR(st.st_mode);
  return DRFRONT_SUCCESS;
}

drfront_status_t drfront_create_dir(const char* path) {
  if (path == NULL)
    return DRFRONT_ERROR_INVALID_PARAMETER;
  if (mkdir(path, 0777) == 0)
    return DRFRONT_SUCCESS;
  if (errno == EEXIST)
    return DRFRONT_ERROR_FILE_EXISTS;
  if (errno == EACCES)
    return DRFRONT_ERROR_ACCESS_DENIED;
  return DRFRONT_ERROR;
}
