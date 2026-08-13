from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from blueprints.auth.decorators import admin_required, login_required
from auth_tokens import current_user_id
from db import get_db
from security import log_admin_action
from uploads import save_upload, validate_upload
from validators import validate_rating, validate_required_text

feedback_bp = Blueprint('feedback', __name__)


@feedback_bp.route('/product/<int:product_id>/feedback', methods=['POST'])
@login_required
def submit_feedback(product_id):
    rating_raw = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    ok, err, rating = validate_rating(rating_raw)
    if ok and not comment and not rating:
        ok, err = False, 'Please add a rating or a comment.'
    if ok and comment:
        ok, err = validate_required_text(comment, 'Comment', min_len=1, max_len=2000)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('customer.product_detail', product_id=product_id))

    media_path, media_type = None, None
    file = request.files.get('media')
    if file and file.filename:
        up_ok, up_err, safe_name, kind = validate_upload(file, allow_video=True)
        if not up_ok:
            flash(up_err, 'error')
            return redirect(url_for('customer.product_detail', product_id=product_id))
        save_upload(file, current_app.config['FEEDBACK_UPLOAD_FOLDER'], safe_name)
        media_path = f'uploads/feedback/{safe_name}'
        media_type = kind

    cur = get_db().cursor()
    cur.execute(
        """
        INSERT INTO ProductFeedback (feedback_id, product_id, user_id, rating, comment_text,
                                      media_path, media_type, created_at)
        VALUES (productfeedback_seq.NEXTVAL, :pid, :p_uid, :r, :c, :mp, :mt, SYSDATE)
        """,
        {'pid': product_id, 'p_uid': current_user_id(), 'r': rating, 'c': comment or None,
         'mp': media_path, 'mt': media_type},
    )
    get_db().commit()
    flash('Thanks for your feedback!', 'success')
    return redirect(url_for('customer.product_detail', product_id=product_id))


@feedback_bp.route('/product-suggestions', methods=['POST'])
@login_required
def submit_product_suggestion():
    description = request.form.get('description', '').strip()
    file = request.files.get('media')
    has_media = bool(file and file.filename)

    if not description and not has_media:
        flash('Please describe the product or attach a picture (or both).', 'error')
        return redirect(request.referrer or url_for('customer.index'))
    if description:
        ok, err = validate_required_text(description, 'Description', min_len=1, max_len=1000)
        if not ok:
            flash(err, 'error')
            return redirect(request.referrer or url_for('customer.index'))

    media_path, media_type = None, None
    if has_media:
        up_ok, up_err, safe_name, kind = validate_upload(file, allow_video=True)
        if not up_ok:
            flash(up_err, 'error')
            return redirect(request.referrer or url_for('customer.index'))
        save_upload(file, current_app.config['FEEDBACK_UPLOAD_FOLDER'], safe_name)
        media_path = f'uploads/feedback/{safe_name}'
        media_type = kind

    cur = get_db().cursor()
    cur.execute(
        """
        INSERT INTO ProductSuggestions (suggestion_id, user_id, description, media_path, media_type, created_at)
        VALUES (productsuggestions_seq.NEXTVAL, :v_uid, :d, :mp, :mt, SYSDATE)
        """,
        {'v_uid': current_user_id(), 'd': description or None, 'mp': media_path, 'mt': media_type},
    )
    get_db().commit()
    flash("Thanks! We've received your suggestion and will look into it.", 'success')
    return redirect(request.referrer or url_for('customer.index'))


@feedback_bp.route('/admin/product-suggestions')
@admin_required
def admin_product_suggestions():
    cur = get_db().cursor()
    cur.execute(
        """
        SELECT s.suggestion_id, u.name, u.email, s.description, s.media_path, s.media_type,
               s.status, s.created_at
        FROM ProductSuggestions s JOIN Users u ON s.user_id = u.user_id
        ORDER BY s.created_at DESC
        """
    )
    suggestions = cur.fetchall()
    return render_template('admin/product_suggestions.html', suggestions=suggestions)


@feedback_bp.route('/admin/product-suggestions/<int:suggestion_id>/status', methods=['POST'])
@admin_required
def update_suggestion_status(suggestion_id):
    status = request.form.get('status')
    if status not in ('new', 'reviewed', 'added'):
        flash('Invalid status.', 'error')
        return redirect(url_for('feedback.admin_product_suggestions'))
    cur = get_db().cursor()
    cur.execute(
        "UPDATE ProductSuggestions SET status = :s WHERE suggestion_id = :sid",
        {'s': status, 'sid': suggestion_id},
    )
    log_admin_action(cur, current_user_id(), 'suggestion.status_update', 'ProductSuggestion', suggestion_id, status)
    get_db().commit()
    flash('Status updated.', 'success')
    return redirect(url_for('feedback.admin_product_suggestions'))


@feedback_bp.route('/admin/feedback')
@admin_required
def admin_feedback_list():
    unreplied_only = request.args.get('unreplied') == '1'
    product_filter = request.args.get('product_id')

    cur = get_db().cursor()
    query = (
        "SELECT f.feedback_id, p.name, p.product_id, u.name, f.rating, f.comment_text, "
        "f.media_path, f.media_type, f.created_at, "
        "(SELECT COUNT(*) FROM FeedbackReplies r WHERE r.feedback_id = f.feedback_id) AS reply_count "
        "FROM ProductFeedback f "
        "JOIN Products p ON f.product_id = p.product_id "
        "JOIN Users u ON f.user_id = u.user_id WHERE 1=1"
    )
    params = {}
    if product_filter:
        query += " AND p.product_id = :pid"
        params['pid'] = int(product_filter)
    query += " ORDER BY f.created_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    if unreplied_only:
        rows = [r for r in rows if r[9] == 0]

    cur.execute("SELECT product_id, name FROM Products ORDER BY name")
    products = cur.fetchall()

    return render_template(
        'admin/feedback.html', feedback_rows=rows, products=products,
        unreplied_only=unreplied_only, selected_product=product_filter,
    )


@feedback_bp.route('/admin/feedback/<int:feedback_id>/reply', methods=['POST'])
@admin_required
def admin_reply_feedback(feedback_id):
    reply_text = request.form.get('reply_text', '').strip()
    ok, err = validate_required_text(reply_text, 'Reply', min_len=1, max_len=2000)
    if not ok:
        flash(err, 'error')
        return redirect(url_for('feedback.admin_feedback_list'))

    media_path, media_type = None, None
    file = request.files.get('media')
    if file and file.filename:
        up_ok, up_err, safe_name, kind = validate_upload(file, allow_video=True)
        if not up_ok:
            flash(up_err, 'error')
            return redirect(url_for('feedback.admin_feedback_list'))
        save_upload(file, current_app.config['FEEDBACK_UPLOAD_FOLDER'], safe_name)
        media_path = f'uploads/feedback/{safe_name}'
        media_type = kind

    cur = get_db().cursor()
    cur.execute(
        """
        INSERT INTO FeedbackReplies (reply_id, feedback_id, admin_user_id, reply_text, media_path,
                                      media_type, created_at)
        VALUES (feedbackreplies_seq.NEXTVAL, :fid, :aid, :rt, :mp, :mt, SYSDATE)
        """,
        {'fid': feedback_id, 'aid': current_user_id(), 'rt': reply_text, 'mp': media_path, 'mt': media_type},
    )
    log_admin_action(cur, current_user_id(), 'feedback.reply', 'ProductFeedback', feedback_id)
    get_db().commit()
    flash('Reply posted.', 'success')
    return redirect(url_for('feedback.admin_feedback_list'))
