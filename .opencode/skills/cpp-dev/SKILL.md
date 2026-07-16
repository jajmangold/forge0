---
name: cpp-dev
description: C/C++ development workflow — cmake, testing with Google Test, sanitizers, static analysis, and memory safety
license: MIT
compatibility: opencode
metadata:
  audience: developers
  language: cpp
---

## What I do

Full C/C++ development workflow with modern build systems, testing, and safety tools.

## When to use me

- Writing C/C++ code
- Building with cmake
- Running tests with Google Test
- Debugging with sanitizers
- Static analysis

## Toolchain

```bash
# Build with cmake
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build

# Build release
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release

# Run tests
ctest --test-dir build
./build/tests  # Direct execution

# Format
clang-format -i src/*.cpp src/*.h
clang-format --dry-run src/*.cpp  # Check only

# Lint
clang-tidy src/*.cpp -- -std=c++17

# Static analysis
cppcheck src/

# Sanitizers (in debug build)
./build/tests  # With ASAN
```

## CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.20)
project(myproject LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build options
option(BUILD_TESTS "Build tests" ON)

# Main library
add_library(mylib src/mylib.cpp)
target_include_directories(mylib PUBLIC include)

# Tests
if(BUILD_TESTS)
    enable_testing()
    find_package(GTest REQUIRED)
    
    add_executable(tests tests/test_mylib.cpp)
    target_link_libraries(tests GTest::gtest_main mylib)
    
    add_test(NAME MyLibTests COMMAND tests)
endif()
```

## Testing with Google Test

```cpp
#include <gtest/gtest.h>
#include "mylib.h"

TEST(MyLibTest, BasicFunctionality) {
    EXPECT_EQ(my_function(1), 2);
}

TEST(MyLibTest, EdgeCases) {
    EXPECT_THROW(my_function(-1), std::invalid_argument);
}

TEST(MyLibTest, PropertyBased) {
    for (int i = 0; i < 1000; i++) {
        EXPECT_GE(my_function(i), 0);
    }
}

// Fixture
class MyLibTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Setup code
    }
    
    void TearDown() override {
        // Cleanup code
    }
};

TEST_F(MyLibTest, WithFixture) {
    EXPECT_TRUE(do_something());
}
```

## Sanitizers

```bash
# AddressSanitizer (memory errors)
cmake -B build -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_FLAGS="-fsanitize=address -fno-omit-frame-pointer"
cmake --build build
./build/tests

# UndefinedBehaviorSanitizer
cmake -B build -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_FLAGS="-fsanitize=undefined"
cmake --build build

# ThreadSanitizer (race conditions)
cmake -B build -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_FLAGS="-fsanitize=thread"
cmake --build build

# MemorySanitizer (uninitialized memory)
cmake -B build -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_FLAGS="-fsanitize=memory -fsanitize-memory-track-origins=2"
cmake --build build
```

## Static Analysis

```cpp
// clang-tidy checks
// .clang-tidy
Checks: >
  -*,
  clang-analyzer-*,
  cppcoreguidelines-*,
  bugprone-*,
  performance-*,
  modernize-*,
  readability-*,
  -modernize-use-trailing-return-type
```

```bash
# Run clang-tidy
clang-tidy src/*.cpp -- -std=c++17 -Iinclude

# Run cppcheck
cppcheck --enable=all --std=c++17 src/
```

## Memory Safety

```cpp
// Use smart pointers
std::unique_ptr<MyClass> ptr = std::make_unique<MyClass>();
std::shared_ptr<MyClass> shared = std::make_shared<MyClass>();

// Use RAII
{
    std::lock_guard<std::mutex> lock(mtx);
    // Mutex automatically released
}

// Use std::optional for nullable
std::optional<int> find_value(const std::vector<int>& v, int target);

// Use std::variant for type safety
std::variant<int, std::string> result = get_value();
```

## Rules

- **Build with cmake** — consistent build system
- **Use Google Test** — comprehensive testing
- **Enable sanitizers in debug** — catch bugs early
- **Run clang-tidy** — enforce best practices
- **Use smart pointers** — no raw owning pointers
- **RAII for all resources** — no manual cleanup
- **Document API** — doxygen comments for public interfaces
