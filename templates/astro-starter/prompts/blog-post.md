---
name: blog-post
target_word_count: 1200
faq_count: 4
---

Write the body for a **blog post** on {brand.display_name}'s site.

# Post topic

- Title: {page.title}
- Primary keyword: `{page.primary_keyword}`
- Search intent: `{page.search_intent}` (informational — the reader is researching, not necessarily hiring yet)
- Related services this post should reference: {post.services}

# Brand context

- Company: {brand.display_name}
- Phone: {brand.phone}
- City: {brand.primary_city}, {brand.primary_state}

# Writing guidance

This is informational content, NOT a sales page. The reader is researching a problem (a leak, a smell, a stain, an insurance question) and trying to understand it before deciding what to do.

Aim for the post to be the kind of page someone bookmarks or shares. That means:

- Lead with the answer, not the throat-clearing. If they searched "what to do when a pipe bursts," tell them in the first 50 words.
- Use specific, tactical advice. "Turn off the main shutoff valve, then..." beats "act quickly."
- Number lists for sequential steps. Bullet lists for parallel options.
- Use scenarios, not abstractions. "If the leak is behind drywall, you'll see..." beats "leaks can be hidden."
- Link concepts to the services {brand.display_name} offers when relevant — but the post itself should be useful even if no service exists.

# Structure

- Lead paragraph that answers the headline question directly (~80-120 words)
- 3-5 `##` subsections covering: the situation, the immediate steps, what NOT to do, when to call a professional, the longer recovery process. Adapt based on the topic.
- A short closing paragraph that points the reader toward action — usually contacting a professional like {brand.display_name} if the situation warrants it.

Target: ~{target_word_count} words.

# FAQ — write {faq_count} pairs

Topics: practical questions a reader who searched this topic would have but the post body didn't fully answer. NOT promotional questions about the company.

Now generate the JSON.
