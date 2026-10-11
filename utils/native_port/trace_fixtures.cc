// Synthetic, redistributable traces for native-host parity. Instructions are
// encoded bytes, never executed on the machine generating or replaying them.
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include "dr_api.h"
#include "trace_entry.h"

using namespace dynamorio::drmemtrace;

struct Instruction {
  uintptr_t pc;
  std::vector<byte> bytes;
  trace_type_t type = TRACE_TYPE_INSTR;
  bool read = false;
  bool write = false;
  uintptr_t address = 0x800000;
  std::vector<byte> regdeps;
};

void record(std::ofstream& out, trace_type_t type, unsigned short size, uintptr_t value) {
  trace_entry_t entry = {};
  entry.type = type;
  entry.size = size;
  entry.addr = value;
  out.write(reinterpret_cast<const char*>(&entry), sizeof(entry));
}

void encoding(std::ofstream& out, const std::vector<byte>& bytes) {
  for (size_t offset = 0; offset < bytes.size(); offset += sizeof(uintptr_t)) {
    trace_entry_t entry = {};
    entry.type = TRACE_TYPE_ENCODING;
    entry.size = std::min(bytes.size() - offset, sizeof(entry.encoding));
    std::memcpy(entry.encoding, bytes.data() + offset, entry.size);
    out.write(reinterpret_cast<const char*>(&entry), sizeof(entry));
  }
}

void describe(void* dc, const char* kind, uintptr_t pc, instr_t* ins) {
  std::cout << kind << " pc=" << std::hex << pc << std::dec
            << " mode=" << instr_get_isa_mode(ins)
            << " category=" << instr_get_category(ins)
            << " operation_size=" << static_cast<unsigned>(instr_get_operation_size(ins))
            << " length=" << instr_length(dc, ins)
            << " src=" << instr_num_srcs(ins) << " dst=" << instr_num_dsts(ins);
  for (int dst = 0; dst < 2; ++dst) {
    int count = dst ? instr_num_dsts(ins) : instr_num_srcs(ins);
    for (int i = 0; i < count; ++i) {
      opnd_t op = dst ? instr_get_dst(ins, i) : instr_get_src(ins, i);
      std::cout << " " << (dst ? "d" : "s") << i << "=" << static_cast<unsigned>(opnd_get_size(op));
      if (opnd_is_reg(op)) std::cout << ":r" << opnd_get_reg(op);
      else if (opnd_is_base_disp(op))
        std::cout << ":m" << opnd_get_base(op) << ":" << opnd_get_index(op)
                  << ":" << opnd_get_scale(op) << ":" << opnd_get_disp(op);
      else if (opnd_is_immed_int(op)) std::cout << ":i" << opnd_get_immed_int(op);
      else if (opnd_is_immed_float(op)) std::cout << ":f" << opnd_get_immed_float(op);
      else if (opnd_is_pc(op)) std::cout << ":pc" << reinterpret_cast<uintptr_t>(opnd_get_pc(op));
      else throw std::runtime_error("unhandled fixture operand");
    }
  }
  std::cout << "\n";
}

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  static_assert(sizeof(trace_entry_t) == 12, "fixtures use the 64-bit wire format");
#ifdef SCARAB_DYNAMIC_DECODER
  void* dc = dr_standalone_init();
#else
  void* dc = GLOBAL_DCONTEXT;
#endif
  std::vector<Instruction> code = {
      {0x400000, {0x48, 0x8b, 0x03}, TRACE_TYPE_INSTR, true},
      {0x400003, {0x48, 0x01, 0xc8}},
      {0x400006, {0x48, 0x89, 0x03}, TRACE_TYPE_INSTR, false, true},
      {0x400009, {0xc5, 0xf8, 0x57, 0xc0}}, // vxorps xmm0,xmm0,xmm0
      {0x40000d, {0xc5, 0xec, 0x58, 0xcb}}, // vaddps ymm1,ymm2,ymm3
      {0x400011, {0xd9, 0xe8}}, // fld1
      {0x400013, {0xd9, 0xe8}}, // fld1
      {0x400015, {0xde, 0xc1}}, // faddp st(1),st(0)
      {0x400017, {0xdd, 0xd8}}, // fstp st(0)
      {0x400019, {0x48, 0x39, 0xc8}},
      {0x40001c, {0x75, 0x04}, TRACE_TYPE_INSTR_CONDITIONAL_JUMP},
      {0x40001e, {0x48, 0x83, 0xc2, 0x01}},
      {0x400022, {0xe8, 0x19, 0x00, 0x00, 0x00}, TRACE_TYPE_INSTR_DIRECT_CALL, false, true, 0x900000},
      {0x400040, {0x48, 0x8b, 0x73, 0x08}, TRACE_TYPE_INSTR, true, false, 0x800008},
      {0x400044, {0xc3}, TRACE_TYPE_INSTR_RETURN, true, false, 0x900000},
      {0x400027, {0xe9, 0xd4, 0xff, 0xff, 0xff}, TRACE_TYPE_INSTR_DIRECT_JUMP},
  };
  for (auto& instruction : code) {
    dr_set_isa_mode(dc, DR_ISA_AMD64, nullptr);
    instr_t x86, deps, roundtrip;
    instr_init(dc, &x86);
    instr_init(dc, &deps);
    instr_init(dc, &roundtrip);
    if (!decode_from_copy(dc, instruction.bytes.data(), reinterpret_cast<byte*>(instruction.pc), &x86))
      throw std::runtime_error("x86 fixture decode failed");
    describe(dc, "x86", instruction.pc, &x86);
    instr_convert_to_isa_regdeps(dc, &x86, &deps);
    alignas(4) byte encoded[MAX_ENCODING_LENGTH] = {};
    byte* end = instr_encode(dc, &deps, encoded);
    if (!end) throw std::runtime_error("REGDEPS fixture encode failed");
    instruction.regdeps.assign(encoded, end);
    dr_set_isa_mode(dc, DR_ISA_REGDEPS, nullptr);
    instr_reset(dc, &roundtrip);
    if (!decode(dc, encoded, &roundtrip)) throw std::runtime_error("REGDEPS fixture decode failed");
    describe(dc, "regdeps", instruction.pc, &roundtrip);
    std::cout << "encoding=";
    for (byte value : instruction.regdeps)
      std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned>(value);
    std::cout << std::dec << "\n";
    instr_free(dc, &x86);
    instr_free(dc, &deps);
    instr_free(dc, &roundtrip);
  }
  for (bool regdeps : {false, true}) {
    const std::string path = std::string(argv[1]) + (regdeps ? "/regdeps.trace" : "/x86.trace");
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot create fixture");
    record(out, TRACE_TYPE_HEADER, 0, TRACE_ENTRY_VERSION);
    record(out, TRACE_TYPE_THREAD, 0, 1);
    record(out, TRACE_TYPE_PID, 0, 1);
    record(out, TRACE_TYPE_MARKER, TRACE_MARKER_TYPE_VERSION, TRACE_ENTRY_VERSION);
    record(out, TRACE_TYPE_MARKER, TRACE_MARKER_TYPE_FILETYPE,
           OFFLINE_FILE_TYPE_ENCODINGS | (regdeps ? OFFLINE_FILE_TYPE_ARCH_REGDEPS : OFFLINE_FILE_TYPE_ARCH_X86_64));
    record(out, TRACE_TYPE_MARKER, TRACE_MARKER_TYPE_CACHE_LINE_SIZE, 64);
    record(out, TRACE_TYPE_MARKER, TRACE_MARKER_TYPE_PAGE_SIZE, 4096);
    record(out, TRACE_TYPE_MARKER, TRACE_MARKER_TYPE_TIMESTAMP, 1000);
    record(out, TRACE_TYPE_MARKER, TRACE_MARKER_TYPE_CPU_ID, 0);
    for (unsigned iteration = 0; iteration < 256; ++iteration) {
      for (const auto& instruction : code) {
        if (instruction.pc == 0x40001e && (iteration & 1)) continue;
        // Exercise both new and cached encodings, including invalidation.
        if (iteration == 0 || iteration == 128)
          encoding(out, regdeps ? instruction.regdeps : instruction.bytes);
        record(out, instruction.type, instruction.bytes.size(), instruction.pc);
        if (instruction.read) record(out, TRACE_TYPE_READ, 8, instruction.address + ((iteration % 8) * 64));
        if (instruction.write) record(out, TRACE_TYPE_WRITE, 8, instruction.address + ((iteration % 8) * 64));
      }
    }
    record(out, TRACE_TYPE_THREAD_EXIT, 0, 1);
    record(out, TRACE_TYPE_FOOTER, 0, 0);
  }
#ifdef SCARAB_DYNAMIC_DECODER
  dr_standalone_exit();
#endif
}
