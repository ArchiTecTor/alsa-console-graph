all: test_capture_audio_rec

test_capture_audio_rec: test_capture_audio_rec.cpp
	gcc -lasound -lrt test_capture_audio_rec.cpp -o test_capture_audio_rec