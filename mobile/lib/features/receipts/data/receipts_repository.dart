import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/receipt.dart';

/// Status event emitted by the backend's SSE /receipts/{id}/events stream.
class ReceiptStatusEvent {
  final String status;            // queued | processing | parsed | error | confirmed
  final String? storeName;
  final double? totalAmount;
  final String? currency;
  final String? processingError;
  final int itemsCount;
  const ReceiptStatusEvent({
    required this.status,
    this.storeName,
    this.totalAmount,
    this.currency,
    this.processingError,
    this.itemsCount = 0,
  });
  bool get isTerminal => status == 'parsed' || status == 'error' || status == 'confirmed';
}

final receiptsRepositoryProvider = Provider<ReceiptsRepository>((ref) {
  return ReceiptsRepository(ref.read(apiClientProvider));
});

class ReceiptsRepository {
  final ApiClient _api;
  ReceiptsRepository(this._api);

  Future<List<Receipt>> listReceipts() async {
    final res = await _api.get(Endpoints.receipts);
    final list = res.data as List<dynamic>;
    return list.map((e) => Receipt.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Receipt> getReceipt(int id) async {
    final res = await _api.get(Endpoints.receiptById(id));
    return Receipt.fromJson(res.data as Map<String, dynamic>);
  }

  Future<int> uploadFromFrame(File imageFile) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(imageFile.path, filename: 'frame.jpg'),
    });
    final res = await _api.post(
      Endpoints.receiptsFromFrame,
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    return res.data['receipt_id'] as int;
  }

  Future<List<int>> uploadFiles(List<File> files) async {
    final formData = FormData();
    for (final f in files) {
      formData.files.add(MapEntry(
        'files',
        await MultipartFile.fromFile(f.path, filename: f.uri.pathSegments.last),
      ));
    }
    final res = await _api.post(
      Endpoints.receiptsUpload,
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    final results = res.data['results'] as List<dynamic>;
    return results.map((r) => r['receipt_id'] as int).toList();
  }

  Future<Map<String, dynamic>> livePreview(File imageFile) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(imageFile.path, filename: 'preview.jpg'),
    });
    final res = await _api.post(
      Endpoints.receiptsLivePreview,
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    return res.data as Map<String, dynamic>;
  }

  Future<Receipt> confirmReceipt(int id, List<Map<String, dynamic>> items) async {
    final res = await _api.patch(Endpoints.receiptConfirm(id), data: {'items': items});
    return Receipt.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> deleteReceipt(int id) async {
    await _api.delete(Endpoints.receiptById(id));
  }

  String receiptImageUrl(int id) => '${_api.dio.options.baseUrl}${Endpoints.receiptImage(id)}';

  String receiptThumbnailUrl(int id) => '${_api.dio.options.baseUrl}${Endpoints.receiptThumbnail(id)}';

  /// Subscribe to the backend's SSE stream for a single receipt's processing
  /// status. Yields one event per status transition; closes when terminal or
  /// after the backend's 60s cap. Caller cancels early by calling
  /// `result.cancel.cancel()` (e.g. when navigating away).
  ({Stream<ReceiptStatusEvent> events, CancelToken cancel}) streamReceiptStatus(int id) {
    final cancelToken = CancelToken();
    final controller = StreamController<ReceiptStatusEvent>();

    () async {
      try {
        final response = await _api.dio.get<ResponseBody>(
          Endpoints.receiptEvents(id),
          cancelToken: cancelToken,
          options: Options(
            responseType: ResponseType.stream,
            receiveTimeout: const Duration(seconds: 90),
            headers: {'Accept': 'text/event-stream'},
          ),
        );

        if (response.data == null) {
          await controller.close();
          return;
        }

        // SSE messages are separated by a blank line ("\n\n"). Each message has
        // optional `event: …` and one or more `data: …` lines. We accumulate
        // bytes, slice on the separator, and parse each block.
        String buffer = '';
        await for (final chunk in response.data!.stream) {
          if (controller.isClosed) break;
          buffer += utf8.decode(chunk, allowMalformed: true);

          int sep;
          while ((sep = buffer.indexOf('\n\n')) != -1) {
            final raw = buffer.substring(0, sep);
            buffer = buffer.substring(sep + 2);

            String eventType = 'message';
            String data = '';
            for (final line in raw.split('\n')) {
              if (line.startsWith('event: ')) {
                eventType = line.substring(7).trim();
              } else if (line.startsWith('data: ')) {
                data += line.substring(6);
              }
            }
            if (data.isEmpty) continue;
            if (eventType == 'status') {
              try {
                final json = jsonDecode(data) as Map<String, dynamic>;
                final ev = ReceiptStatusEvent(
                  status: (json['status'] ?? 'queued') as String,
                  storeName: json['store_name'] as String?,
                  totalAmount: (json['total_amount'] as num?)?.toDouble(),
                  currency: json['currency'] as String?,
                  processingError: json['processing_error'] as String?,
                  itemsCount: (json['items_count'] ?? 0) as int,
                );
                controller.add(ev);
                if (ev.isTerminal) {
                  await controller.close();
                  return;
                }
              } catch (_) {
                // Malformed event payload — skip rather than crash the stream.
              }
            } else if (eventType == 'timeout' || eventType == 'gone') {
              await controller.close();
              return;
            }
          }
        }
        await controller.close();
      } catch (e) {
        if (!controller.isClosed) {
          controller.addError(e);
          await controller.close();
        }
      }
    }();

    return (events: controller.stream, cancel: cancelToken);
  }
}
