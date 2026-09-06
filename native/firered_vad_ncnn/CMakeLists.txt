cmake_minimum_required(VERSION 3.10)
project(transcriber_firered_vad_ncnn LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT DEFINED NCNN_ROOT OR NCNN_ROOT STREQUAL "")
  message(FATAL_ERROR "NCNN_ROOT must point to the pinned NCNN 20260113 installation or build tree")
endif()

set(NCNN_REQUIRED_VERSION "20260113")
set(NCNN_INCLUDE_DIR "${NCNN_ROOT}/include/ncnn")
set(NCNN_LIBRARY "${NCNN_ROOT}/lib/libncnn.a")
set(NCNN_VERSION_FILE "${NCNN_ROOT}/lib/cmake/ncnn/ncnnConfigVersion.cmake")

if(NOT EXISTS "${NCNN_INCLUDE_DIR}/net.h")
  message(FATAL_ERROR "pinned NCNN header not found at ${NCNN_INCLUDE_DIR}/net.h")
endif()
if(NOT EXISTS "${NCNN_LIBRARY}")
  message(FATAL_ERROR "pinned static NCNN library not found at ${NCNN_LIBRARY}")
endif()
if(NOT EXISTS "${NCNN_VERSION_FILE}")
  message(FATAL_ERROR "NCNN version provenance not found at ${NCNN_VERSION_FILE}")
endif()

unset(PACKAGE_VERSION)
include("${NCNN_VERSION_FILE}")
if(NOT DEFINED PACKAGE_VERSION OR NOT PACKAGE_VERSION STREQUAL NCNN_REQUIRED_VERSION)
  message(FATAL_ERROR
    "NCNN installation reports version '${PACKAGE_VERSION}'; expected pinned version ${NCNN_REQUIRED_VERSION}")
endif()

find_package(Threads REQUIRED)
set(UPSTREAM_FRONTEND "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/firered-vad/runtime-common-frontend")

add_executable(firered-vad-ncnn
  controller/main.cpp
  composition/application.cpp
  service/run_inference.cpp
  protocol/runner_command.cpp
  protocol/probability_json.cpp
  infrastructure/firered_frontend_adapter.cpp
  infrastructure/upstream_cmvn_adapter.cpp
  infrastructure/ncnn_inference.cpp
  "${UPSTREAM_FRONTEND}/fft.cc"
)
target_include_directories(firered-vad-ncnn PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}"
  "${NCNN_INCLUDE_DIR}"
)
target_link_libraries(firered-vad-ncnn PRIVATE "${NCNN_LIBRARY}" Threads::Threads)
if(NOT WIN32)
  target_link_libraries(firered-vad-ncnn PRIVATE m)
endif()
