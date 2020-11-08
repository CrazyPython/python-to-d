public import std.variant;
auto broaden(T)(T input) {
    import std.traits;
    import std.range;
    import std.conv;
    static if (isArray!(T)) {
        static if (!is(ElementType!T == Variant)) {
            static if (is(ElementType!T == void)) {
                if (input.length == 0)
                    return Variant(variantArray());
                else {
                    // void[] arrays are unsupported
                    assert(0);
                }
            } else return Variant(to!(Variant[])(input));
        } else return Variant(input);
    } else static if (is(input == Variant)) {
        return input;
    } else {
        return Variant(input);
    }
}
auto commonTypeOrVariantArray(Args...)(Args args) {
    import std.conv; import std.traits;
    // could support static arrays
    // could be more optimized by preallocating
    static if (allSameType!(Args)) {
        Args[0][] result;
    } else {
        Variant[] result;
    }
    foreach (arg; args) {
        result ~= arg;
    }
    return result;
}

// commonOrVariantArray finds the common type or it returna a variant array