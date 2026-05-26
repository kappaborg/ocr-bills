class User {
  final int id;
  final String email;
  final DateTime? createdAt;

  const User({required this.id, required this.email, this.createdAt});

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as int,
        email: json['email'] as String,
        createdAt: json['created_at'] != null
            ? DateTime.tryParse(json['created_at'] as String)
            : null,
      );
}
