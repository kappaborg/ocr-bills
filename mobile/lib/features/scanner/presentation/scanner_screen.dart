import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../features/receipts/data/receipts_repository.dart';
import '../../../features/receipts/providers/receipts_provider.dart';
import 'widgets/camera_overlay.dart';

class ScannerScreen extends ConsumerStatefulWidget {
  const ScannerScreen({super.key});

  @override
  ConsumerState<ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends ConsumerState<ScannerScreen> with WidgetsBindingObserver {
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  bool _permissionGranted = false;
  bool _uploading = false;
  FlashMode _flashMode = FlashMode.off;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _requestPermissionAndInit();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (_controller == null || !_controller!.value.isInitialized) return;
    if (state == AppLifecycleState.inactive) {
      _controller!.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _initCamera(_cameras.isNotEmpty ? _cameras.first : null);
    }
  }

  Future<void> _requestPermissionAndInit() async {
    final status = await Permission.camera.request();
    if (status.isGranted) {
      setState(() => _permissionGranted = true);
      _cameras = await availableCameras();
      if (_cameras.isNotEmpty) await _initCamera(_cameras.first);
    } else {
      setState(() => _permissionGranted = false);
    }
  }

  Future<void> _initCamera(CameraDescription? cam) async {
    if (cam == null) return;
    final ctrl = CameraController(cam, ResolutionPreset.high, enableAudio: false);
    try {
      await ctrl.initialize();
      if (!mounted) return;
      setState(() => _controller = ctrl);
    } catch (_) {}
  }

  Future<void> _toggleFlash() async {
    final next = _flashMode == FlashMode.off ? FlashMode.torch : FlashMode.off;
    await _controller?.setFlashMode(next);
    setState(() => _flashMode = next);
  }

  Future<void> _capture() async {
    if (_controller == null || _uploading) return;
    setState(() => _uploading = true);
    try {
      final xFile = await _controller!.takePicture();
      final file = File(xFile.path);
      // Show live preview bottom sheet first
      await _sendPreview(file);
      // Then upload for real
      if (mounted) await _uploadFile(file);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _sendPreview(File file) async {
    try {
      final repo = ref.read(receiptsRepositoryProvider);
      final result = await repo.livePreview(file);
      if (mounted) {
        await _showPreviewSheet(result);
      }
    } catch (_) {}
  }

  Future<void> _showPreviewSheet(Map<String, dynamic> data) async {
    await showModalBottomSheet(
      context: context,
      builder: (_) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Preview', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            if (data['store_name'] != null) Text('Store: ${data['store_name']}'),
            if (data['total_amount'] != null) Text('Total: ${data['total_amount']} ${data['currency'] ?? ''}'),
            const SizedBox(height: 16),
            FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Upload Receipt')),
          ],
        ),
      ),
    );
  }

  Future<void> _uploadFile(File file) async {
    try {
      final repo = ref.read(receiptsRepositoryProvider);
      final receiptId = await repo.uploadFromFrame(file);
      if (mounted) {
        ref.invalidate(receiptsListProvider);
        context.push('/receipt/$receiptId');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Upload failed: $e'), backgroundColor: Colors.red));
      }
    }
  }

  Future<void> _pickFromGallery() async {
    final picker = ImagePicker();
    final xFile = await picker.pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (xFile == null) return;
    setState(() => _uploading = true);
    try {
      await _uploadFile(File(xFile.path));
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_permissionGranted) {
      return _PermissionView(onRequest: _requestPermissionAndInit);
    }
    if (_controller == null || !_controller!.value.isInitialized) {
      return const Scaffold(backgroundColor: Colors.black, body: Center(child: CircularProgressIndicator(color: Colors.white)));
    }

    return Theme(
      data: ThemeData.dark(),
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(
          fit: StackFit.expand,
          children: [
            CameraPreview(_controller!),
            const CameraOverlay(),
            SafeArea(
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Row(
                      children: [
                        const Text('Scan Receipt', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                        const Spacer(),
                        IconButton(
                          icon: Icon(_flashMode == FlashMode.off ? Icons.flash_off : Icons.flash_on, color: Colors.white),
                          onPressed: _toggleFlash,
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 40),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        IconButton(
                          icon: const Icon(Icons.photo_library, color: Colors.white, size: 32),
                          onPressed: _uploading ? null : _pickFromGallery,
                        ),
                        GestureDetector(
                          onTap: _uploading ? null : _capture,
                          child: Container(
                            width: 72,
                            height: 72,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 4),
                              color: _uploading ? Colors.grey : Colors.white24,
                            ),
                            child: _uploading
                                ? const Padding(padding: EdgeInsets.all(20), child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3))
                                : const SizedBox.shrink(),
                          ),
                        ),
                        const SizedBox(width: 48),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PermissionView extends StatelessWidget {
  final VoidCallback onRequest;
  const _PermissionView({required this.onRequest});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.camera_alt, size: 72),
              const SizedBox(height: 16),
              const Text('Camera permission required', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text('Please allow camera access to scan receipts', textAlign: TextAlign.center),
              const SizedBox(height: 24),
              FilledButton(onPressed: onRequest, child: const Text('Grant Permission')),
            ],
          ),
        ),
      ),
    );
  }
}
