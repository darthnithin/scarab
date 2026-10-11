// Exercise the real socket transport under stream fragmentation and interruption.
// Build with -DGTEST_COMPILE to expose both sides of the transport.
#include "pin/pin_lib/message_queue_interface_lib.h"
#include <cassert>
#include <cerrno>
#include <cstring>
#include <signal.h>
#include <sys/time.h>
#include <sys/wait.h>

class Probe : public TCPSocket {
 public:
  using TCPSocket::send;
  using TCPSocket::scarab_receive;
  using TCPSocket::pin_receive;
};

static void write_all(int fd, const char* bytes, size_t size, size_t chunk) {
  while(size) {
    ssize_t count = write(fd, bytes, std::min(size, chunk));
    if(count < 0 && errno == EINTR) continue;
    assert(count > 0);
    bytes += count;
    size -= count;
  }
}

static std::vector<char> frame(const std::vector<char>& payload) {
  uint32_t n = payload.size();
  std::vector<char> bytes = {'S', 'C', 'B', '1', char(n >> 24), char(n >> 16),
                              char(n >> 8), char(n)};
  bytes.insert(bytes.end(), payload.begin(), payload.end());
  return bytes;
}

static void wait_ok(pid_t child, bool success = true) {
  int status = 0;
  assert(waitpid(child, &status, 0) == child);
  assert(WIFEXITED(status));
  assert((WEXITSTATUS(status) == 0) == success);
}

static void fragmented(size_t n, bool fixed) {
  int fd[2];
  assert(socketpair(AF_UNIX, SOCK_STREAM, 0, fd) == 0);
  std::vector<char> payload(n);
  for(size_t i = 0; i < n; ++i) payload[i] = char(i * 37);
  pid_t child = fork();
  assert(child >= 0);
  if(!child) {
    close(fd[0]);
    auto bytes = frame(payload);
    write_all(fd[1], bytes.data(), bytes.size(), 3);
    close(fd[1]);
    _exit(0);
  }
  close(fd[1]);
  Probe probe;
  auto received = fixed ? probe.pin_receive(fd[0], n) : probe.scarab_receive(fd[0]);
  assert(received == payload);
  close(fd[0]);
  wait_ok(child);
}

static void coalesced() {
  int fd[2];
  assert(socketpair(AF_UNIX, SOCK_STREAM, 0, fd) == 0);
  auto bytes = frame({'a', 'b'});
  auto second = frame({'c', 'd', 'e'});
  bytes.insert(bytes.end(), second.begin(), second.end());
  write_all(fd[1], bytes.data(), bytes.size(), bytes.size());
  Probe probe;
  assert(probe.scarab_receive(fd[0]) == std::vector<char>({'a', 'b'}));
  assert(probe.pin_receive(fd[0], 3) == std::vector<char>({'c', 'd', 'e'}));
  close(fd[0]); close(fd[1]);
}

static void rejected(std::vector<char> bytes, bool fixed = false) {
  int fd[2];
  assert(socketpair(AF_UNIX, SOCK_STREAM, 0, fd) == 0);
  fflush(nullptr);
  pid_t child = fork();
  assert(child >= 0);
  if(!child) {
    close(fd[1]);
    Probe probe;
    if(fixed) probe.pin_receive(fd[0], 20);
    else probe.scarab_receive(fd[0]);
    _exit(0);
  }
  close(fd[0]);
  write_all(fd[1], bytes.data(), bytes.size(), bytes.size());
  close(fd[1]);
  wait_ok(child, false);
}

static void ignore_alarm(int) {}

static void interrupted_send(bool framed) {
  setenv("SCARAB_SOCKET_PROTOCOL", framed ? "framed-v1" : "legacy", 1);
  int fd[2];
  assert(socketpair(AF_UNIX, SOCK_STREAM, 0, fd) == 0);
  int small = 1024;
  assert(setsockopt(fd[0], SOL_SOCKET, SO_SNDBUF, &small, sizeof(small)) == 0);
  std::vector<char> payload(MAX_PACKET_SIZE);
  for(size_t i = 0; i < payload.size(); ++i) payload[i] = char(i * 17);
  auto expected = framed ? frame(payload) : payload;
  pid_t child = fork();
  assert(child >= 0);
  if(!child) {
    close(fd[0]);
    std::vector<char> received;
    char buffer[127];
    while(received.size() < expected.size()) {
      ssize_t count = read(fd[1], buffer, sizeof(buffer));
      assert(count > 0);
      received.insert(received.end(), buffer, buffer + count);
      usleep(1000);
    }
    assert(received == expected);
    close(fd[1]);
    _exit(0);
  }
  close(fd[1]);
  struct sigaction action = {};
  action.sa_handler = ignore_alarm;
  sigemptyset(&action.sa_mask);
  assert(sigaction(SIGALRM, &action, nullptr) == 0);
  struct itimerval timer = {};
  timer.it_interval.tv_usec = 500;
  timer.it_value = timer.it_interval;
  assert(setitimer(ITIMER_REAL, &timer, nullptr) == 0);
  Probe probe;
  probe.send(fd[0], &payload);
  timer = {};
  assert(setitimer(ITIMER_REAL, &timer, nullptr) == 0);
  close(fd[0]);
  wait_ok(child);
}

int main() {
  alarm(20);
  Message<std::vector<uint32_t>> vector_message(std::vector<uint32_t>{1, 2, 3});
  vector_message = std::vector<uint32_t>{4};
  assert(std::vector<uint32_t>(vector_message) == std::vector<uint32_t>({4}));
  Message<std::deque<uint32_t>> deque_message(std::deque<uint32_t>{1, 2, 3});
  deque_message = std::deque<uint32_t>{4};
  assert(std::deque<uint32_t>(deque_message) == std::deque<uint32_t>({4}));
  setenv("SCARAB_SOCKET_PROTOCOL", "framed-v1", 1);
  for(size_t n : {size_t(0), size_t(1), size_t(20), size_t(MAX_PACKET_SIZE)}) {
    fragmented(n, false);
    fragmented(n, true);
  }
  coalesced();
  rejected({'b', 'a', 'd', '!', 0, 0, 0, 0});
  rejected({'S', 'C', 'B', '1', 0, 1, 0, 0});
  rejected({'S', 'C', 'B', '1', 0, 0, 0, 2, 'x'});
  rejected(frame({'x'}), true);
  interrupted_send(true);
  interrupted_send(false);
  static_assert(sizeof(Scarab_To_Pin_Msg) == 20, "Pin command ABI changed");
  static_assert(sizeof(Pin_Reg_Val) == 24, "Pin register ABI changed");
  printf("PASS: fragmented/coalesced frames, malformed/truncated frames, interrupted partial writes, message reuse\n");
  printf("ABI: command=%zu register=%zu operation=%zu\n", sizeof(Scarab_To_Pin_Msg),
         sizeof(Pin_Reg_Val), sizeof(compressed_op));
}
